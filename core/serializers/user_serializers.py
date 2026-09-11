"""
User-related DRF serializers using UserService
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from core.models import User
from core.services.user_service import UserService
from .base import TenantAwareSerializer


class UserSerializer(TenantAwareSerializer):
    """
    Base User serializer for general operations
    """
    service_class = UserService
    
    # Computed fields
    full_name = serializers.SerializerMethodField()
    tenant_names = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_admin', 'last_login', 'created_at',
            'updated_at', 'full_name', 'tenant_names'
        ]
        read_only_fields = [
            'id', 'last_login', 'created_at', 'updated_at',
            'full_name', 'tenant_names'
        ]
    
    def get_full_name(self, obj):
        """Get user's full name"""
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def get_tenant_names(self, obj):
        """Get names of tenants user has access to"""
        try:
            return [tenant.name for tenant in obj.tenants.all()]
        except AttributeError:
            return []
    
    def validate_username(self, value):
        """Validate username"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters long")
        
        # Check for valid characters (alphanumeric, underscore, hyphen)
        if not value.replace('_', '').replace('-', '').isalnum():
            raise serializers.ValidationError("Username can only contain letters, numbers, underscores, and hyphens")
        
        return value.strip().lower()
    
    def validate_email(self, value):
        """Validate email format"""
        if value and '@' not in value:
            raise serializers.ValidationError("Invalid email format")
        return value.lower() if value else value


class UserCreateSerializer(TenantAwareSerializer):
    """
    Serializer for creating new users with password
    """
    service_class = UserService
    
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_admin', 'password', 'password_confirm'
        ]
        extra_kwargs = {
            'username': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'email': {'required': True},
        }
    
    def validate_password(self, value):
        """Validate password strength"""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, attrs):
        """Validate password confirmation"""
        password = attrs.get('password')
        password_confirm = attrs.pop('password_confirm', None)
        
        if password != password_confirm:
            raise serializers.ValidationError("Passwords do not match")
        
        return super().validate(attrs)
    
    def validate_username(self, value):
        """Validate username uniqueness"""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters long")
        
        value = value.strip().lower()
        
        # Check uniqueness across all tenants
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        
        return value
    
    def _service_create(self, service, validated_data):
        """Create user using UserService"""
        password = validated_data.pop('password')
        
        # Create user through service
        user = service.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=password,
            is_admin=validated_data.get('is_admin', False),
            is_active=validated_data.get('is_active', True)
        )
        
        return user


class UserUpdateSerializer(TenantAwareSerializer):
    """
    Serializer for updating existing users (without password)
    """
    service_class = UserService
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'is_active', 'is_admin'
        ]
    
    def validate_username(self, value):
        """Username changes not allowed in update"""
        if self.instance and self.instance.username != value:
            raise serializers.ValidationError("Username cannot be changed")
        return value
    
    def _service_update(self, service, instance, validated_data):
        """Update user using UserService"""
        return service.update_user(str(instance.id), **validated_data)


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password change operations
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True, min_length=8)
    
    def validate_new_password(self, value):
        """Validate new password strength"""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value
    
    def validate(self, attrs):
        """Validate password confirmation and old password"""
        new_password = attrs.get('new_password')
        new_password_confirm = attrs.get('new_password_confirm')
        old_password = attrs.get('old_password')
        
        if new_password != new_password_confirm:
            raise serializers.ValidationError("New passwords do not match")
        
        # Validate old password
        user = self.context.get('user')
        if not user or not user.check_password(old_password):
            raise serializers.ValidationError("Current password is incorrect")
        
        return attrs
    
    def save(self):
        """Change password using UserService"""
        tenant = self.context.get('tenant')
        user = self.context.get('user')
        
        if not tenant or not user:
            raise serializers.ValidationError("Invalid context")
        
        service = UserService(tenant)
        service.change_password(str(user.id), self.validated_data['new_password'])
        
        return user


class UserProfileSerializer(TenantAwareSerializer):
    """
    Serializer for user profile operations (self-service)
    """
    service_class = UserService
    
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'last_login', 'created_at', 'full_name'
        ]
        read_only_fields = [
            'id', 'username', 'last_login', 'created_at', 'full_name'
        ]
    
    def get_full_name(self, obj):
        """Get user's full name"""
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def _service_update(self, service, instance, validated_data):
        """Update user profile using UserService"""
        # Only allow certain fields to be updated by user themselves
        allowed_fields = ['email', 'first_name', 'last_name']
        update_data = {k: v for k, v in validated_data.items() if k in allowed_fields}
        
        return service.update_user(str(instance.id), **update_data)


class UserTenantSerializer(serializers.Serializer):
    """
    Serializer for managing user-tenant relationships
    """
    user_id = serializers.UUIDField()
    tenant_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=['add', 'remove'])
    
    def validate(self, attrs):
        """Validate user and tenant exist"""
        from core.models import School
        
        try:
            user = User.objects.get(id=attrs['user_id'])
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        
        try:
            tenant = School.objects.get(id=attrs['tenant_id'])
            attrs['tenant'] = tenant
        except School.DoesNotExist:
            raise serializers.ValidationError("Tenant not found")
        
        return attrs
    
    def save(self):
        """Perform user-tenant relationship operation"""
        user = self.validated_data['user']
        tenant = self.validated_data['tenant']
        action = self.validated_data['action']
        
        service = UserService(tenant)
        
        if action == 'add':
            service.add_user_to_tenant(str(user.id), tenant)
        elif action == 'remove':
            service.remove_user_from_tenant(str(user.id), tenant)
        
        return user


class UserListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for user lists
    """
    full_name = serializers.SerializerMethodField()
    tenant_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'email', 'is_active',
            'is_admin', 'last_login', 'tenant_count'
        ]
    
    def get_full_name(self, obj):
        """Get user's full name"""
        return f"{obj.first_name} {obj.last_name}".strip()
    
    def get_tenant_count(self, obj):
        """Get count of tenants user has access to (prefers queryset annotation)."""
        annotated = getattr(obj, 'tenant_count_anno', None)
        if annotated is not None:
            return annotated
        try:
            return obj.tenants.count()
        except AttributeError:
            return 0