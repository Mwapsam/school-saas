"""
Custom permissions for DRF API views following Django best practices.

DEPRECATED for new code: prefer ``core.authz.drf.HasPermission("<codename>")``,
which resolves against the RBAC role system (see :mod:`core.authz`). The
``is_teacher`` / ``can_view_reports`` attributes referenced by some classes
below never existed on the User model — those branches are always False.
``TenantAccessPermission`` is still current and unrelated to RBAC.
"""
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


class TenantAccessPermission(permissions.BasePermission):
    """
    Permission class to ensure users can only access data from their tenant
    """
    message = "You don't have permission to access this tenant's data."
    
    def has_permission(self, request, view):
        """
        Check if user has basic tenant access
        """
        # Authenticated users only
        if not request.user.is_authenticated:
            return False
        
        # Check if tenant context exists
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        # Check if user belongs to this tenant
        if hasattr(request.user, 'tenants'):
            return request.user.tenants.filter(id=tenant.id).exists()
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """
        Check if user can access specific object
        """
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        # Check if object belongs to user's tenant
        if hasattr(obj, 'tenant'):
            return obj.tenant == tenant
        elif hasattr(obj, 'school'):
            return obj.school == tenant
        
        return True


class IsAdminUser(permissions.BasePermission):
    """
    Permission requiring `is_admin=True` for every request, read or write.
    """
    message = "You must be an admin user to access this resource."

    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, 'is_admin', False)


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to only allow admin users to edit objects
    Regular users can only read
    """
    message = "You must be an admin user to perform this action."
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        return request.user.is_authenticated and getattr(request.user, 'is_admin', False)


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to allow users to edit their own objects or admins to edit any
    """
    message = "You can only access your own data unless you're an admin."
    
    def has_object_permission(self, request, view, obj):
        # Admin users can access anything
        if getattr(request.user, 'is_admin', False):
            return True
        
        # Users can access their own objects
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'created_by'):
            return obj.created_by == request.user
        
        return False


class IsTeacherOrAdmin(permissions.BasePermission):
    """
    Permission for teacher-level access
    """
    message = "You must be a teacher or admin to perform this action."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        return (
            getattr(request.user, 'is_admin', False) or 
            getattr(request.user, 'is_teacher', False)
        )


class CanManageStudents(permissions.BasePermission):
    """
    Permission for student management operations
    """
    message = "You don't have permission to manage students."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions for admin and teachers only
        return (
            getattr(request.user, 'is_admin', False) or 
            getattr(request.user, 'is_teacher', False)
        )


class CanManageAdmissions(permissions.BasePermission):
    """
    Permission for admission management operations
    """
    message = "You don't have permission to manage admissions."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Admission management requires admin access
        return getattr(request.user, 'is_admin', False)


class CanAccessReports(permissions.BasePermission):
    """
    Permission for accessing reports
    """
    message = "You don't have permission to access reports."
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Reports require at least teacher level access
        return (
            getattr(request.user, 'is_admin', False) or 
            getattr(request.user, 'is_teacher', False) or
            getattr(request.user, 'can_view_reports', False)
        )