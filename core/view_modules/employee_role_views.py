"""HR → Employee profile → "Roles & Access" tab.

Lets an HR admin see which portal login an employee has and assign RBAC roles
(from :mod:`core.authz.registry` via :class:`~core.models.Role`) to that login,
without leaving the HR module. The heavy lifting — activating/deactivating
:class:`~core.models.UserRoleAssignment` rows and the break-glass guard — lives
in :meth:`core.services.role_service.RoleService.set_user_roles`.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods

from core.authz.access import has_permission
from core.authz.mixins import require_permission
from core.models import Employee
from core.services.exceptions import BusinessLogicException, NotFoundException, ValidationException
from core.services.role_service import RoleService

PERM = "settings.users.manage"


def _login_user(employee):
    """The employee's portal login, or None. A ``user`` pointing at an admin
    account is a historical mis-link and treated as "no dedicated login"."""
    u = getattr(employee, "user", None)
    return u if (u and not u.is_admin) else None


def _render_fragment(request, tenant, employee_id):
    employee = Employee.objects.select_related("user").get(tenant=tenant, id=employee_id)
    login = _login_user(employee)
    svc = RoleService(tenant)
    all_roles = list(svc.list_roles(include_inactive=False))
    held_ids = (
        set(str(r.id) for r in svc.roles_for_user(login.id)) if login else set()
    )
    portal_roles = []
    if login:
        try:
            from portal.roles import resolve_roles
            portal_roles = resolve_roles(login).ordered()
        except Exception:  # portal app optional / resolution failure — non-fatal
            portal_roles = []

    return render_to_string(
        "core/htmx/hr/employee_roles_tab.html",
        {
            "employee": employee,
            "employee_id": str(employee_id),
            "login": login,
            "roles": [
                {"role": r, "held": str(r.id) in held_ids, "system": r.is_system}
                for r in all_roles
            ],
            "portal_roles": portal_roles,
            "can_manage": has_permission(request.user, tenant, PERM, request=request),
        },
        request=request,
    )


@login_required
@require_permission("hr.employee.view")
def employee_roles_tab(request, employee_id):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return JsonResponse({"error": "Tenant not found"}, status=400)
    try:
        return HttpResponse(_render_fragment(request, tenant, employee_id))
    except Employee.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)


@require_http_methods(["POST"])
@login_required
@require_permission(PERM)
def employee_roles_update_api(request, employee_id):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return JsonResponse({"error": "Tenant not found"}, status=400)
    try:
        employee = Employee.objects.select_related("user").get(
            tenant=tenant, id=employee_id
        )
    except Employee.DoesNotExist:
        return JsonResponse({"error": "Employee not found"}, status=404)

    login = _login_user(employee)
    if not login:
        return JsonResponse(
            {"error": "This employee has no portal login yet. Create one from "
                      "User Management before assigning roles."},
            status=400,
        )

    try:
        RoleService(tenant).set_user_roles(
            login.id,
            request.POST.getlist("role_ids"),
            assigned_by_id=request.user.id,
            user=request.user,
        )
    except BusinessLogicException as e:
        return JsonResponse({"error": str(e.message)}, status=400)
    except (ValidationException, NotFoundException) as e:
        return JsonResponse({"error": str(e.message)}, status=400)

    return HttpResponse(_render_fragment(request, tenant, employee_id))
