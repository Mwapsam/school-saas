"""Gate the server-rendered staff dashboard (the `core` app, mounted at "/")
to `is_admin` accounts only.

Teachers and parents authenticate exclusively through the separate `portal`
app (JWT, mounted at /api/portal/, gated by portal.roles/portal.permissions).
They must never reach the Django dashboard, regardless of whether a given
view remembered to add its own login/permission check.

Scope: only requests that resolve into the `core` URL namespace are gated
here. The core app mounts a handful of its own dashboard AJAX endpoints
under paths that happen to start with "/api/" (e.g. /api/attendance/summary/,
still `core:attendance_summary_api`) — those are dashboard surface and are
gated too. The *separate* DRF app at /api/v1/... (core.api_urls, registered
with no namespace) is intentionally left alone: it already has its own
per-viewset DRF permission_classes, and those need to keep working with
DRF-native authentication (SessionAuthentication + force_authenticate in
tests, JWT, Basic) that a Django-level, session-cookie-only middleware like
this one cannot see into.

/api/teacher-comments/ is a similar exception: save_teacher_comments_api and
get_teacher_comments_api (core/views.py) are explicitly shared verbatim
between the session-authenticated staff exam-group page and the
JWT-authenticated Next.js teacher portal (see their docstrings). They already
enforce their own DRF `IsAuthenticated` check, so — like /api/portal/ — they
must not be gated to `is_admin` here; this middleware runs before DRF's JWT
authentication, so a JWT-only (session-less) teacher request would otherwise
always look anonymous at this point and get redirected to login.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.urls import Resolver404, resolve

_SKIP_PREFIXES = (
    "/admin/",
    "/api/portal/",
    "/api/teacher-comments/",
    "/static/",
    "/media/",
    "/accounts/",
    "/webhooks/quickbooks/",
)

_PUBLIC_DASHBOARD_URL_NAMES = {
    "core:portal_landing",
    "core:portal_admission_register",
    "core:portal_admission_success",
    "core:portal_status_check",
    "core:admission_register",
    "core:admission_register_submit",
    "core:admission_register_success",
    "core:admission_step_navigate",
    "core:admission_status_check",
    "core:admission_apply",
    "core:admission_success",
    "core:admission_status_api",
}


class DashboardAccessMiddleware:
    """Default-deny gate: `core`-namespaced dashboard requests require `is_admin`."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        if path.startswith(_SKIP_PREFIXES):
            return self.get_response(request)

        try:
            match = resolve(path)
        except Resolver404:
            return self.get_response(request)

        if match.namespace != "core":
            return self.get_response(request)

        url_name = f"{match.namespace}:{match.url_name}"
        if url_name in _PUBLIC_DASHBOARD_URL_NAMES:
            return self.get_response(request)

        if request.user.is_authenticated and getattr(request.user, "is_admin", False):
            return self.get_response(request)

        if request.user.is_authenticated:
            return render(
                request,
                "registration/portal_only.html",
                {"portal_app_url": settings.PORTAL_APP_URL},
                status=403,
            )

        return redirect_to_login(request.get_full_path())


class ModuleAccessMiddleware:
    """
    Enforce module-level access control for template-based dashboard views.

    This middleware runs after tenant resolution and auth to check whether
    a requested URL belongs to a module that is enabled for the current school/tenant.

    If a URL is mapped in core.module_urls.URL_MODULE_MAP to a module, that module
    must be enabled in SchoolModule for the request to proceed. If disabled, returns
    a 403 response (portal-only page for HTML, JSON error for API requests).

    Root users (is_root=True) bypass module access control as a break-glass measure.
    Ordinary administrators do NOT bypass — module enablement is a separate axis from
    permission/role-based access control.

    Unmapped URLs (not in URL_MODULE_MAP) are allowed to proceed unchanged.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        try:
            match = resolve(path)
        except Resolver404:
            return self.get_response(request)

        url_name = match.url_name
        if not url_name:
            return self.get_response(request)

        from core.module_urls import URL_MODULE_MAP
        from core.modules import enabled_modules_for

        module = URL_MODULE_MAP.get(url_name)
        if not module:
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user and getattr(user, "is_root", False):
            return self.get_response(request)

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return self._deny_access(request)

        if module not in enabled_modules_for(tenant, request=request):
            return self._deny_access(request)

        return self.get_response(request)

    @staticmethod
    def _deny_access(request):
        accept = request.META.get("HTTP_ACCEPT", "text/html")
        if "application/json" in accept:
            from django.http import JsonResponse

            return JsonResponse(
                {"error": "This module is not enabled for your school"},
                status=403,
            )
        else:
            return render(
                request,
                "registration/portal_only.html",
                {"portal_app_url": settings.PORTAL_APP_URL},
                status=403,
            )
