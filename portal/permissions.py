"""DRF permissions for the portal, expressed purely in terms of resolved roles.

A user may hold several roles at once. Each ``_RolePermission`` subclass scopes
one endpoint to one role: it checks membership (not equality) and then pins
``request.role_context`` to *that* role's profile, so views can keep reading
``request.role_context.profile`` unchanged regardless of the user's other roles.
"""
from rest_framework.permissions import BasePermission

from core.services.configuration_service import portal_feature_enabled

from .roles import hr_permissions_for, resolve_roles


class _RolePermission(BasePermission):
    required_role: str = ""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        roleset = resolve_roles(request.user)
        request.role_set = roleset
        if not roleset.has(self.required_role):
            return False
        # Pin the per-endpoint context so views/serializers don't re-resolve and
        # always see the profile for THIS role.
        request.role_context = roleset.context_for(self.required_role)
        return True


class IsParent(_RolePermission):
    message = "This endpoint is only available to parents/guardians."
    required_role = "parent"


class IsTeacher(_RolePermission):
    message = "This endpoint is only available to teachers."
    required_role = "teacher"


class IsLibrarian(_RolePermission):
    message = "This endpoint is only available to librarians."
    required_role = "librarian"


class IsHR(_RolePermission):
    message = "This endpoint is only available to HR users."
    required_role = "hr"


class HasHRPermission(BasePermission):
    """Require one or more ``hr.*`` codenames on top of the ``hr`` role.

    Usage::

        class ContractListView(APIView):
            permission_classes = [IsHR, HasHRPermission("hr.contract.view")]

    SAFE methods are allowed when the user holds any of ``read_codenames``
    (defaults to ``codenames``); unsafe methods require ``codenames``.
    ``require_all=False`` -> any one code is enough.
    """

    message = "You do not have permission for this HR action."
    code = "hr_permission_denied"

    def __init__(self, *codenames, read=None, require_all=False):
        self.codenames = tuple(codenames)
        self.read_codenames = tuple(read) if read is not None else self.codenames
        self.require_all = require_all

    # DRF instantiates permission classes with no args; support both
    # ``HasHRPermission("x")`` (already an instance) and bare class use.
    def __call__(self):
        return self

    def has_permission(self, request, view):
        from rest_framework.permissions import SAFE_METHODS

        needed = self.read_codenames if request.method in SAFE_METHODS else self.codenames
        if not needed:
            return True
        held = hr_permissions_for(request.user)
        check = all if self.require_all else any
        return check(code in held for code in needed)


class IsLinkedEmployee(BasePermission):
    """Any authenticated user with an active linked ``Employee`` (self-service)."""

    message = "This endpoint is only available to employees."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        roleset = resolve_roles(request.user)
        request.role_set = roleset
        employee = roleset.employee
        if employee is None:
            return False
        request.employee = employee
        return True


class PortalFeatureRequired(BasePermission):
    """Gate a parent endpoint on a :class:`core.models.PortalFeatureAccess`
    toggle. Set ``required_feature`` on the view (not the permission), e.g.::

        class ChildAttendanceView(_ChildScopedView):
            required_feature = "attendance"

    Missing config row => enabled (opt-out, not opt-in). Runs after the role
    permission, so ``request.role_context`` is already populated.
    """

    message = "This section is not available for your school."
    code = "feature_disabled"

    def has_permission(self, request, view):
        feature = getattr(view, "required_feature", None)
        if not feature:
            return True
        ctx = getattr(request, "role_context", None)
        if ctx is None:
            roleset = resolve_roles(request.user)
            ctx = roleset.context_for(roleset.primary)
        tenant = getattr(getattr(ctx, "profile", None), "tenant", None)
        if tenant is None:
            return True
        return portal_feature_enabled(tenant, feature)


class IsPortalUser(BasePermission):
    message = "Your account is not enabled for the portal."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        roleset = resolve_roles(request.user)
        request.role_set = roleset
        request.role_context = roleset.context_for(roleset.primary)
        return roleset.is_portal_user
