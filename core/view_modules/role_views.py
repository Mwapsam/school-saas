"""Role & permission management UI (``/settings/roles/``).

A role is a named bag of permission codenames (see :mod:`core.authz.registry`).
System roles are seeded per tenant and cannot be deleted or renamed, but their
permission sets can be edited. Assignment of roles to users happens on the User
Management screen (``core:user_management``).
"""
from __future__ import annotations

from django.http import JsonResponse, HttpResponse, Http404
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, TemplateView

from core.authz.mixins import PermissionRequiredMixin, require_permission
from core.authz.registry import permissions_by_module
from core.models import Role, UserRoleAssignment
from core.services.role_service import RoleService
from core.services.exceptions import (
    BusinessLogicException, DuplicateException, NotFoundException, ValidationException,
)

PERM = 'settings.roles.manage'


def _tenant(request):
    return getattr(request, 'tenant', None)


def _role_rows(tenant):
    """[(role, codename_count, assignee_count), ...] for the list table."""
    roles = RoleService(tenant).list_roles()
    counts = {}
    for a in UserRoleAssignment.objects.filter(tenant=tenant, is_active=True).values_list('role_id', flat=True):
        counts[a] = counts.get(a, 0) + 1
    return [(r, len(r.codenames), counts.get(r.id, 0)) for r in roles]


class RoleListView(PermissionRequiredMixin, ListView):
    template_name = 'core/settings/roles/list.html'
    context_object_name = 'role_rows'
    required_permission = PERM

    def get_queryset(self):
        tenant = _tenant(self.request)
        return _role_rows(tenant) if tenant else []


class RoleDetailView(PermissionRequiredMixin, TemplateView):
    template_name = 'core/settings/roles/detail.html'
    required_permission = PERM

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        if not tenant:
            raise Http404('No tenant')
        role = RoleService(tenant).get_role(kwargs['pk'])
        granted = set(role.codenames)
        ctx['role'] = role
        ctx['modules'] = [
            {
                'key': key,
                'label': label,
                'items': [
                    {'codename': c, 'label': lbl, 'granted': c in granted}
                    for c, lbl in items
                ],
            }
            for key, label, items in permissions_by_module()
        ]
        ctx['granted_count'] = len(granted)
        return ctx


def _list_fragment(request, tenant):
    return HttpResponse(render_to_string(
        'core/settings/roles/_list.html', {'role_rows': _role_rows(tenant)}, request=request,
    ))


@require_http_methods(["POST"])
@login_required
@require_permission(PERM)
def role_create_api(request):
    tenant = _tenant(request)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        RoleService(tenant).create_role(
            name=request.POST.get('name', ''),
            description=request.POST.get('description', '').strip(),
            codenames=request.POST.getlist('codenames'),
            user=request.user,
        )
        return _list_fragment(request, tenant)
    except DuplicateException as e:
        return JsonResponse({'name': [str(e.message)]}, status=400)
    except ValidationException as e:
        return JsonResponse(e.details or {'error': [e.message]}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission(PERM)
def role_update_api(request, pk):
    tenant = _tenant(request)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        RoleService(tenant).update_role(
            pk,
            name=request.POST.get('name'),
            description=request.POST.get('description'),
            user=request.user,
        )
        return JsonResponse({'success': True})
    except (BusinessLogicException, DuplicateException, ValidationException) as e:
        return JsonResponse({'error': str(e.message)}, status=400)
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


@require_http_methods(["POST"])
@login_required
@require_permission(PERM)
def role_set_permissions_api(request, pk):
    tenant = _tenant(request)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        role = RoleService(tenant).set_permissions(pk, request.POST.getlist('codenames'), user=request.user)
        return JsonResponse({'success': True, 'count': len(role.codenames)})
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


@require_http_methods(["POST"])
@login_required
@require_permission(PERM)
def role_delete_api(request, pk):
    tenant = _tenant(request)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        RoleService(tenant).delete_role(pk, user=request.user)
        return _list_fragment(request, tenant)
    except BusinessLogicException as e:
        return JsonResponse({'error': str(e.message)}, status=400)
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)
