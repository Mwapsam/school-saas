"""DRF permission class factory built on the authz black box.

Usage in a viewset::

    from core.authz.drf import HasPermission, ModuleEnabled
    permission_classes = [ModuleEnabled("hr"), TenantAccessPermission, HasPermission("hr.employee.manage")]

Module enabled is checked BEFORE business permissions, so disabled modules return 403
before the user ever reaches permission checks.

Or method-scoped::

    permission_classes = [HasPermission(
        read="hr.employee.view", write="hr.employee.manage",
    )]
"""
from __future__ import annotations

from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from .access import get_permission_set


def HasPermission(*codenames, read=None, write=None, require_all=False):
    read_codes = list(codenames) if codenames else ([read] if read else [])
    write_codes = [write] if write else list(codenames)

    class _HasPermission(permissions.BasePermission):
        message = "You do not have permission to perform this action."

        def has_permission(self, request, view):
            user = getattr(request, "user", None)
            if user is None or not user.is_authenticated:
                return False
            granted = get_permission_set(
                user, getattr(request, "tenant", None), request=request
            )
            needed = read_codes if request.method in permissions.SAFE_METHODS else write_codes
            if not needed:
                return bool(granted)
            check = all if require_all else any
            return check(code in granted for code in needed)

    _HasPermission.__name__ = "HasPermission(%s)" % ",".join(
        sorted(set(read_codes) | set(write_codes))
    )
    return _HasPermission


class ModuleEnabled(permissions.BasePermission):
    """
    Permission class that checks if a specific module is enabled for the current tenant.

    This is a first-class security boundary: if a module is disabled for a school,
    the entire viewset/endpoint returns 403 regardless of the user's role or permissions.
    This prevents accidental exposure of disabled features and ensures clean separation
    between enabled/disabled product areas.

    Usage in a viewset::

        class EmployeeViewSet(viewsets.ModelViewSet):
            permission_classes = [
                IsAuthenticated,
                ModuleEnabled("hr"),  # ← Checked BEFORE business permissions
                HasPermission("hr.employee.manage"),
            ]
            module = "hr"  # ← Also set this so disabled modules can be discovered

    The 'module' class attribute on the viewset determines which SchoolModule is checked.
    """
    message = "This module is not enabled for your school."

    def has_permission(self, request, view):
        """
        Check if the module specified on the viewset is enabled for the current tenant.
        Returns False (403) if disabled or if the viewset doesn't specify a module.
        """
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False

        # Get the module from the viewset class attribute
        module_key = getattr(view, "module", None)
        if not module_key:
            # If the viewset doesn't declare a module, it's not module-gated
            return True

        # Check if this module is enabled for the tenant
        from core.models import SchoolModule
        try:
            school_module = SchoolModule.objects.get(
                school=tenant,
                module=module_key
            )
            return school_module.enabled
        except SchoolModule.DoesNotExist:
            # If the module row doesn't exist, it's disabled by default
            return False
