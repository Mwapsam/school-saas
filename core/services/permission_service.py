from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from django.contrib.auth.models import AnonymousUser

from .base import TenantAwareService
from .exceptions import PermissionException, ServiceException
from .logging_service import ServiceLogger, logged_operation


class PermissionServiceInterface(ABC):
    """Abstract interface for permission services - replaceable black box"""
    
    @abstractmethod
    def can_user_access_tenant(self, user: Any, tenant: Any) -> bool:
        """Check if user has access to a specific tenant"""
        pass
    
    @abstractmethod
    def can_user_perform_action(self, user: Any, action: str, resource: str, obj: Any = None) -> bool:
        """Check if user can perform an action on a resource"""
        pass
    
    @abstractmethod
    def get_user_permissions(self, user: Any, tenant: Any) -> List[str]:
        """Get list of permissions for user in tenant"""
        pass
    
    @abstractmethod
    def has_role(self, user: Any, role: str, tenant: Any = None) -> bool:
        """Check if user has a specific role"""
        pass


class DjangoPermissionService(PermissionServiceInterface):
    """Django-specific implementation of permission service"""
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.logger = ServiceLogger('permissions', tenant)
    
    @logged_operation(action='check', resource_type='tenant_access')
    def can_user_access_tenant(self, user: Any, tenant: Any) -> bool:
        """Check if user has access to tenant using Django auth"""
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return False
        
        if not tenant:
            return False
        
        # Check if user belongs to this tenant
        if hasattr(user, 'tenants'):
            return user.tenants.filter(id=tenant.id).exists()
        
        # Fallback for admin users
        return getattr(user, 'is_superuser', False)
    
    @logged_operation(action='check', resource_type='action_permission')
    def can_user_perform_action(self, user: Any, action: str, resource: str, obj: Any = None) -> bool:
        """Check action permissions using Django's permission system"""
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return False
        
        # Admin users can do everything
        if getattr(user, 'is_admin', False) or getattr(user, 'is_superuser', False):
            return True
        
        # Define permission mappings
        permission_map = {
            'view': self._can_view,
            'add': self._can_add,
            'change': self._can_change,
            'delete': self._can_delete,
            'manage': self._can_manage
        }
        
        permission_check = permission_map.get(action, lambda u, r, o: False)
        return permission_check(user, resource, obj)
    
    def get_user_permissions(self, user: Any, tenant: Any) -> List[str]:
        """Get user's permissions in tenant"""
        if not self.can_user_access_tenant(user, tenant):
            return []
        
        permissions = []
        
        # Basic permissions for authenticated users
        if user.is_authenticated:
            permissions.extend(['view_dashboard', 'view_profile'])
        
        # Admin permissions
        if getattr(user, 'is_admin', False):
            permissions.extend([
                'manage_students', 'manage_employees', 'manage_courses',
                'manage_admissions', 'view_reports', 'manage_settings'
            ])
        
        # Teacher permissions
        if getattr(user, 'is_teacher', False):
            permissions.extend([
                'view_students', 'manage_attendance', 'manage_grades',
                'view_reports'
            ])
        
        return permissions
    
    def has_role(self, user: Any, role: str, tenant: Any = None) -> bool:
        """Check if user has specific role"""
        if not user or isinstance(user, AnonymousUser):
            return False
        
        if tenant and not self.can_user_access_tenant(user, tenant):
            return False
        
        role_checks = {
            'admin': lambda u: getattr(u, 'is_admin', False),
            'teacher': lambda u: getattr(u, 'is_teacher', False),
            'student': lambda u: hasattr(u, 'student_profile'),
            'parent': lambda u: hasattr(u, 'guardian_profile'),
            'staff': lambda u: getattr(u, 'is_staff', False)
        }
        
        check_function = role_checks.get(role, lambda u: False)
        return check_function(user)
    
    # Private helper methods
    def _can_view(self, user: Any, resource: str, obj: Any = None) -> bool:
        """Check view permissions"""
        # Most authenticated users can view basic resources
        if resource in ['students', 'courses', 'batches']:
            return (getattr(user, 'is_admin', False) or 
                    getattr(user, 'is_teacher', False))
        
        # Reports require special permission
        if resource == 'reports':
            return (getattr(user, 'is_admin', False) or 
                    getattr(user, 'is_teacher', False) or
                    getattr(user, 'can_view_reports', False))
        
        return getattr(user, 'is_admin', False)
    
    def _can_add(self, user: Any, resource: str, obj: Any = None) -> bool:
        """Check add permissions"""
        if resource in ['students', 'employees']:
            return getattr(user, 'is_admin', False)
        
        if resource in ['courses', 'batches', 'subjects']:
            return (getattr(user, 'is_admin', False) or 
                    getattr(user, 'is_teacher', False))
        
        return getattr(user, 'is_admin', False)
    
    def _can_change(self, user: Any, resource: str, obj: Any = None) -> bool:
        """Check change permissions"""
        # Check if user owns the object
        if obj and hasattr(obj, 'user') and obj.user == user:
            return True
        
        if obj and hasattr(obj, 'created_by') and obj.created_by == user:
            return True
        
        # Admin and teacher permissions
        if resource in ['students', 'attendance', 'grades']:
            return (getattr(user, 'is_admin', False) or 
                    getattr(user, 'is_teacher', False))
        
        return getattr(user, 'is_admin', False)
    
    def _can_delete(self, user: Any, resource: str, obj: Any = None) -> bool:
        """Check delete permissions"""
        # Most delete operations require admin
        return getattr(user, 'is_admin', False)
    
    def _can_manage(self, user: Any, resource: str, obj: Any = None) -> bool:
        """Check management permissions"""
        if resource == 'admissions':
            return getattr(user, 'is_admin', False)
        
        if resource in ['students', 'attendance']:
            return (getattr(user, 'is_admin', False) or 
                    getattr(user, 'is_teacher', False))
        
        return getattr(user, 'is_admin', False)


class PermissionService(TenantAwareService):
    """Service facade for permission operations"""
    
    def __init__(self, tenant, permission_implementation: PermissionServiceInterface = None):
        super().__init__(None, tenant)  # No model for permission service
        self.implementation = permission_implementation or DjangoPermissionService(tenant)
        self.logger = ServiceLogger('permission_facade', tenant)
    
    def check_tenant_access(self, user: Any) -> bool:
        """Check if user can access current tenant"""
        return self.implementation.can_user_access_tenant(user, self.tenant)
    
    def require_tenant_access(self, user: Any) -> None:
        """Require tenant access or raise exception"""
        if not self.check_tenant_access(user):
            raise PermissionException(
                "User does not have access to this tenant",
                details={
                    "user": str(user),
                    "tenant": str(self.tenant)
                }
            )
    
    def check_action_permission(self, user: Any, action: str, resource: str, obj: Any = None) -> bool:
        """Check if user can perform action on resource"""
        return self.implementation.can_user_perform_action(user, action, resource, obj)
    
    def require_permission(self, user: Any, action: str, resource: str, obj: Any = None) -> None:
        """Require permission or raise exception"""
        if not self.check_action_permission(user, action, resource, obj):
            raise PermissionException(
                f"User does not have permission to {action} {resource}",
                details={
                    "user": str(user),
                    "action": action,
                    "resource": resource,
                    "tenant": str(self.tenant)
                }
            )
    
    def get_user_permissions(self, user: Any) -> List[str]:
        """Get all permissions for user"""
        return self.implementation.get_user_permissions(user, self.tenant)
    
    def user_has_role(self, user: Any, role: str) -> bool:
        """Check if user has specific role"""
        return self.implementation.has_role(user, role, self.tenant)