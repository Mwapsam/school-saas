import logging
import secrets
from typing import Optional, Dict, Any
from datetime import timedelta
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.core.mail import send_mail

from core.models import User, PasswordResetToken
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateException,
    BusinessLogicException,
    PermissionException
)
from .logging_service import ServiceLogger, logged_operation

logger = logging.getLogger(__name__)


class UserService(TenantAwareService[User]):    
    def __init__(self, tenant):
        super().__init__(User, tenant)
        self.logger = ServiceLogger('user', tenant)
    
    @logged_operation(action='create', resource_type='user', log_result=True)
    @transaction.atomic
    def create_user(
        self,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
        password: str,
        is_admin: bool = False,
        is_active: bool = True,
        user: User = None,
        **additional_data
    ) -> User:
        if self.exists(username=username):
            raise DuplicateException(
                f"User with username '{username}' already exists in this school",
                details={"username": username, "tenant": self.tenant.name}
            )
        
        if is_admin and user and not user.is_admin:
            raise PermissionException(
                "Only admin users can create other admin users",
                details={"requesting_user": user.username, "target_admin": True}
            )
        
        created_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin,
            is_active=is_active,
            **additional_data
        )
        # Standard Django password field so the account authenticates through
        # ModelBackend (used by the admin login and the portal's JWT login).
        created_user.set_password(password)
        created_user.save()
        created_user.tenants.add(self.tenant)

        self.logger.log_create(
            resource_type='user',
            resource_id=str(created_user.id),
            user=user,
            details={
                'username': username,
                'email': email,
                'is_admin': is_admin,
                'is_active': is_active
            }
        )
        
        return created_user
    
    def authenticate_user(
        self,
        username: str,
        password: str,
        request=None
    ) -> Optional[User]:
        try:
            user = self.get_or_none(username=username, is_active=True)
            
            if not user:
                self.logger.log_security_event(
                    event_type='authentication_failed',
                    severity='MEDIUM',
                    request=request,
                    details={'username': username, 'reason': 'user_not_found'}
                )
                return None
            
            if check_password(password, user.password_hash):
                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])
                
                self.logger.log_action(
                    action='authenticate',
                    resource_type='user',
                    resource_id=str(user.id),
                    user=user,
                    request=request,
                    details={'result': 'success'},
                    level='INFO'
                )
                
                return user
            else:
                self.logger.log_security_event(
                    event_type='authentication_failed',
                    severity='MEDIUM',
                    user=user,
                    request=request,
                    details={'username': username, 'reason': 'invalid_password'}
                )
                return None
                
        except Exception as e:
            self.logger.log_error(
                error=e,
                action='authenticate',
                resource_type='user',
                request=request,
                additional_context={'username': username}
            )
            return None
    
    def get_user_by_username(self, username: str) -> User:
        user = self.get_or_none(username=username)
        if user is None:
            raise NotFoundException(
                f"User with username '{username}' not found",
                details={"username": username, "tenant": self.tenant.name}
            )
        return user
    
    @logged_operation(action='update', resource_type='user')
    def update_user(
        self,
        user_id: str,
        performing_user: User = None,
        **update_data
    ) -> User:
        target_user = self.get_by_id(user_id)
        
        sensitive_fields = ['is_admin', 'is_active', 'password']
        if any(field in update_data for field in sensitive_fields):
            if not performing_user or not performing_user.is_admin:
                raise PermissionException(
                    "Only admin users can modify sensitive fields",
                    details={
                        "performing_user": performing_user.username if performing_user else None,
                        "target_user": target_user.username,
                        "sensitive_fields": [f for f in sensitive_fields if f in update_data]
                    }
                )
        
        if 'username' in update_data:
            new_username = update_data['username']
            if new_username != target_user.username:
                if self.exists(username=new_username):
                    raise DuplicateException(
                        f"Username '{new_username}' already exists",
                        details={"username": new_username}
                    )
        
        if 'password' in update_data:
            update_data['password'] = make_password(update_data.pop('password'))
        
        changed_fields = {}
        for field, value in update_data.items():
            if hasattr(target_user, field):
                old_value = getattr(target_user, field)
                if old_value != value:
                    changed_fields[field] = {'old': old_value, 'new': value}
        
        updated_user = self.update(user_id, **update_data)
        
        self.logger.log_update(
            resource_type='user',
            resource_id=str(updated_user.id),
            user=performing_user,
            changed_fields=changed_fields
        )
        
        return updated_user
    
    @logged_operation(action='change_password', resource_type='user')
    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str,
        performing_user: User = None,
        force_change: bool = False
    ) -> User:
        target_user = self.get_by_id(user_id)
        
        is_self = performing_user and str(performing_user.id) == str(user_id)
        is_admin_force = (performing_user and performing_user.is_admin and 
                         force_change and not is_self)
        
        if not is_self and not is_admin_force:
            raise PermissionException(
                "Users can only change their own password, or admin can force change",
                details={
                    "performing_user": performing_user.username if performing_user else None,
                    "target_user": target_user.username
                }
            )
        
        if not force_change:
            if not check_password(old_password, target_user.password):
                self.logger.log_security_event(
                    event_type='password_change_failed',
                    severity='MEDIUM',
                    user=target_user,
                    details={'reason': 'invalid_old_password'}
                )
                raise PermissionException(
                    "Current password is incorrect",
                    details={"user_id": user_id}
                )
        
        if len(new_password) < 6:
            raise ValidationException(
                "Password must be at least 6 characters long",
                details={"min_length": 6, "provided_length": len(new_password)}
            )
        
        new_password_hash = make_password(new_password)
        updated_user = self.update(user_id, password=new_password_hash)
        
        self.logger.log_action(
            action='change_password',
            resource_type='user',
            resource_id=str(updated_user.id),
            user=performing_user,
            details={
                'target_user': target_user.username,
                'force_change': force_change
            },
            level='INFO'
        )
        
        return updated_user
    
    @logged_operation(action='deactivate', resource_type='user')
    def deactivate_user(
        self,
        user_id: str,
        performing_user: User = None,
        reason: str = None
    ) -> User:
        target_user = self.get_by_id(user_id)
        
        if not performing_user or not performing_user.is_admin:
            raise PermissionException(
                "Only admin users can deactivate accounts",
                details={"performing_user": performing_user.username if performing_user else None}
            )
        
        if target_user.is_admin:
            active_admin_count = self.count(is_admin=True, is_active=True)
            if active_admin_count <= 1:
                raise BusinessLogicException(
                    "Cannot deactivate the last admin user",
                    details={"admin_count": active_admin_count}
                )
        
        updated_user = self.update(user_id, is_active=False)
        
        self.logger.log_action(
            action='deactivate',
            resource_type='user',
            resource_id=str(updated_user.id),
            user=performing_user,
            details={
                'target_user': target_user.username,
                'reason': reason
            },
            level='WARNING'
        )
        
        return updated_user

    @staticmethod
    def hard_delete_user_record(user: User) -> None:
        """Actually delete a ``User`` row, bypassing django-tenant-users'
        soft-delete guard.

        ``User.delete()`` is overridden by django-tenant-users to always raise
        ``DeleteError`` and point callers at ``UserProfile.objects.delete_user()``
        — which doesn't hard-delete at all, it just unlinks tenants and sets
        ``is_active=False``. Any code in this project that needs a genuine hard
        delete (permanently removing an account, cleaning up a duplicate
        guardian's login, etc.) should route through this instead of calling
        ``user.delete()`` directly.

        Note: ``School`` (``TENANT_MODEL``) extends django-tenants'
        ``TenantMixin`` directly, not tenant_users' ``TenantBase`` — this
        project never uses ``add_user``/``remove_user``/``UserTenantPermissions``
        or tenant ownership, just the plain ``tenants`` M2M. So unlinking here
        is a straight ``.clear()``, not the ``TenantBase.remove_user`` dance.
        """
        user.tenants.clear()
        user.delete(force_drop=True)

    @logged_operation(action='permanently_delete', resource_type='user')
    @transaction.atomic
    def permanently_delete_user(
        self,
        user_id: str,
        performing_user: User = None
    ) -> tuple[bool, str]:
        """Permanently delete a user account and all cascade-linked records
        (admission notes, status history, messages, privilege grants).

        Profile records (Employee/Student/Guardian) are NOT deleted — they just
        lose their login link (User FK is SET_NULL).

        Returns (success, message) tuple.
        """
        target_user = self.get_by_id(user_id)

        if not performing_user or not performing_user.is_admin:
            raise PermissionException(
                "Only admin users can delete accounts",
                details={"performing_user": performing_user.username if performing_user else None}
            )

        if target_user.is_admin:
            active_admin_count = self.count(is_admin=True, is_active=True)
            if active_admin_count <= 1:
                raise BusinessLogicException(
                    "Cannot delete the last admin user",
                    details={"admin_count": active_admin_count}
                )

        # Log the deletion BEFORE the user is deleted, so the audit trail captures it
        self.logger.log_action(
            action='permanently_delete',
            resource_type='user',
            resource_id=str(target_user.id),
            user=performing_user,
            details={
                'target_user': target_user.username,
                'email': target_user.email,
            },
            level='CRITICAL'
        )

        # Attempt the hard delete; catch ProtectedError if any FK relation
        # unexpectedly has on_delete=PROTECT (defensive, none currently apply).
        try:
            username = target_user.username
            self.hard_delete_user_record(target_user)
            return (True, f"User '{username}' has been permanently deleted.")
        except Exception as e:
            # If a PROTECT constraint exists, return the error message instead of raising
            if 'PROTECT' in str(e).upper() or 'protected' in str(e).lower():
                return (False, f"Cannot delete user: {str(e)}")
            # Re-raise unexpected exceptions
            raise

    def reactivate_user(
        self,
        user_id: str,
        performing_user: User = None
    ) -> User:
        target_user = self.get_by_id(user_id)
        
        if not performing_user or not performing_user.is_admin:
            raise PermissionException(
                "Only admin users can reactivate accounts",
                details={"performing_user": performing_user.username if performing_user else None}
            )
        
        updated_user = self.update(user_id, is_active=True)
        
        self.logger.log_action(
            action='reactivate',
            resource_type='user',
            resource_id=str(updated_user.id),
            user=performing_user,
            details={'target_user': target_user.username},
            level='INFO'
        )
        
        return updated_user
    
    def get_active_users(self) -> QuerySet[User]:
        return self.filter(is_active=True)
    
    def get_admin_users(self) -> QuerySet[User]:
        return self.filter(is_admin=True, is_active=True)
    
    def search_users(
        self,
        query: str,
        active_only: bool = True,
        limit: int = None
    ) -> QuerySet[User]:
        search_filter = (
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(email__icontains=query)
        )
        
        if active_only:
            search_filter &= Q(is_active=True)
        
        queryset = self.filter(search_filter)
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    def get_user_statistics(self) -> Dict[str, Any]:
        stats = {
            'total_users': self.count(),
            'active_users': self.count(is_active=True),
            'inactive_users': self.count(is_active=False),
            'admin_users': self.count(is_admin=True, is_active=True),
            'regular_users': self.count(is_admin=False, is_active=True)
        }
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        stats['recent_active_users'] = self.count(
            is_active=True,
            last_login__gte=thirty_days_ago
        )
        
        return stats
    
    def _validate_create_data(self, data: Dict[str, Any]) -> None:
        super()._validate_create_data(data)
        
        required_fields = ['username', 'email', 'first_name', 'last_name']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationException(
                    f"Required field '{field}' is missing or empty",
                    details={"field": field}
                )
        
        email = data.get('email')
        if email and '@' not in email:
            raise ValidationException(
                "Invalid email format",
                details={"email": email}
            )
        
        username = data.get('username')
        if username and len(username) < 3:
            raise ValidationException(
                "Username must be at least 3 characters long",
                details={"username": username, "min_length": 3}
            )

    @logged_operation(action='request_password_reset', resource_type='user')
    def request_password_reset(
        self,
        email: str,
        reset_url_template: str
    ) -> None:
        user = self.get_or_none(email=email, is_active=True)
        if not user:
            self.logger.log_action(
                action='request_password_reset',
                resource_type='user',
                details={'email': email, 'result': 'user_not_found'},
                level='INFO'
            )
            return

        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=24)

        PasswordResetToken.objects.filter(user=user).delete()
        reset_token = PasswordResetToken.objects.create(
            user=user,
            token=token,
            expires_at=expires_at
        )

        reset_url = reset_url_template.format(token=token)

        try:
            send_mail(
                subject='Password Reset Request',
                message=f"""
Dear {user.first_name},

You have requested to reset your password. Click the link below to proceed:

{reset_url}

This link will expire in 24 hours.

If you did not request this, please ignore this email.

Best regards,
{school_name} Portal
                """.format(school_name=self.tenant.name if self.tenant else "School Portal"),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=False,
            )

            self.logger.log_action(
                action='request_password_reset',
                resource_type='user',
                resource_id=str(user.id),
                user=user,
                details={'email': user.email, 'result': 'email_sent'},
                level='INFO'
            )
        except Exception as e:
            self.logger.log_error(
                error=e,
                action='request_password_reset',
                resource_type='user',
                resource_id=str(user.id),
                additional_context={'email': user.email}
            )
            raise BusinessLogicException(
                "Failed to send password reset email",
                details={"email": user.email}
            )

    @logged_operation(action='confirm_password_reset', resource_type='user')
    @transaction.atomic
    def confirm_password_reset(
        self,
        token: str,
        new_password: str
    ) -> User:
        if len(new_password) < 6:
            raise ValidationException(
                "Password must be at least 6 characters long",
                details={"min_length": 6, "provided_length": len(new_password)}
            )

        try:
            reset_token = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            raise NotFoundException(
                "Invalid or expired password reset token",
                details={"token": token[:10] + "..."}
            )

        if not reset_token.is_valid():
            reset_token.delete()
            raise NotFoundException(
                "Password reset token has expired or already been used",
                details={"token": token[:10] + "..."}
            )

        user = reset_token.user
        new_password_hash = make_password(new_password)
        updated_user = self.update(str(user.id), password=new_password_hash)

        reset_token.is_used = True
        reset_token.save()

        self.logger.log_action(
            action='confirm_password_reset',
            resource_type='user',
            resource_id=str(updated_user.id),
            user=updated_user,
            details={'result': 'success'},
            level='INFO'
        )

        return updated_user