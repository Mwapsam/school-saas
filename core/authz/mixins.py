"""View-level enforcement built on :func:`core.authz.access.has_permission`.

  * ``PermissionRequiredMixin``  — for class-based dashboard views
  * ``require_permission(code)`` — decorator for function-based API endpoints

Both preserve the existing behaviour: HTML views redirect anonymous users to
login and render the 403 "portal only" page for a signed-in user who lacks
access; JSON APIs return ``{"error": ...}`` with status 403. ``is_root`` users
always pass (break-glass bypass in ``access._compute``); ``is_admin`` alone only
grants dashboard entry — a role carrying the codename is still required.
"""
from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import render

from .access import get_permission_set


def _has(request, required, *, require_all):
    if isinstance(required, str):
        required = [required]
    granted = get_permission_set(
        getattr(request, "user", None),
        getattr(request, "tenant", None),
        request=request,
    )
    if not required:
        return bool(granted)
    check = all if require_all else any
    return check(code in granted for code in required)


def _deny_html(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    return render(
        request,
        "registration/portal_only.html",
        {"portal_app_url": settings.PORTAL_APP_URL},
        status=403,
    )


class PermissionRequiredMixin:
    """Set ``required_permission = "hr.employee.view"`` or
    ``required_permissions = [...]`` (with ``require_all_permissions`` to switch
    from any-of to all-of). Falls through to the view when the check passes."""

    required_permission: "str | None" = None
    required_permissions: "list[str] | None" = None
    require_all_permissions: bool = False

    def get_required_permissions(self):
        if self.required_permissions is not None:
            return list(self.required_permissions)
        if self.required_permission:
            return [self.required_permission]
        return []

    def dispatch(self, request, *args, **kwargs):
        if not _has(
            request,
            self.get_required_permissions(),
            require_all=self.require_all_permissions,
        ):
            return _deny_html(request)
        return super().dispatch(request, *args, **kwargs)


def require_permission(*codenames, require_all=False):
    """Decorator for FBV API endpoints. 403 JSON on failure."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not _has(request, list(codenames), require_all=require_all):
                return JsonResponse(
                    {"error": "You do not have permission to perform this action"},
                    status=403,
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


class ModuleAccessMixin:
    """Enforce module enablement for class-based views.

    Set ``required_module = "hr"`` on the view class.
    Returns 403 "portal only" page if the module is not enabled for the school.
    """

    required_module: "str | None" = None

    def dispatch(self, request, *args, **kwargs):
        if not self.required_module:
            return super().dispatch(request, *args, **kwargs)

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return _deny_html(request)

        # Check if module is enabled for this tenant
        from core.models import SchoolModule
        try:
            school_module = SchoolModule.objects.get(
                school=tenant,
                module=self.required_module
            )
            if not school_module.enabled:
                return _deny_html(request)
        except SchoolModule.DoesNotExist:
            # Module row doesn't exist = module is disabled
            return _deny_html(request)

        return super().dispatch(request, *args, **kwargs)
