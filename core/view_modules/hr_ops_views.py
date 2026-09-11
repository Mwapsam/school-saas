"""HR operations screens for the classic admin: HR tasks, policy documents +
acknowledgement tracking, and the HR audit trail.

Reuses ``core.services.hr_task_service`` / ``hr_policy_service``; the audit
viewer reads ``core.models.HRAuditLog`` directly (write-only elsewhere).
"""
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, TemplateView

from core.authz.access import get_permission_set
from core.authz.mixins import PermissionRequiredMixin, require_permission
from core.models import Employee, HRAuditLog, HRTask, PolicyDocument
from core.services.exceptions import NotFoundException, ValidationException
from core.services.hr_policy_service import PolicyService
from core.services.hr_task_service import HRTaskService

TASK_NEXT = {"pending": "in_progress", "in_progress": "completed", "completed": "pending"}


def _tenant(request):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise Http404("School not found")
    return tenant


def _perms(request):
    return get_permission_set(request.user, getattr(request, "tenant", None))


def _date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationException("Dates must be in YYYY-MM-DD format.")


def _err(exc, status=400):
    return JsonResponse({"error": str(getattr(exc, "message", exc))}, status=status)


def _choices(model, field):
    return model._meta.get_field(field).choices or []


# ══ HR tasks ══════════════════════════════════════════════════════════════

def _render_tasks(request, tenant):
    tasks = HRTaskService(tenant).list_tasks(
        status=request.GET.get("status") or None,
        category=request.GET.get("category") or None,
    )
    return render_to_string("core/htmx/hr/task_list_content.html", {
        "request": request, "tasks": tasks,
        "can_manage": "hr.tasks.manage" in _perms(request),
        "task_next": TASK_NEXT,
    })


class HRTaskListView(PermissionRequiredMixin, ListView):
    required_permissions = ["hr.tasks.manage", "hr.employee.view"]
    template_name = "core/hr/ops/task_list.html"
    htmx_template_name = "core/htmx/hr/task_list_content.html"
    context_object_name = "tasks"
    paginate_by = 30

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get("HX-Request") == "true"
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return HRTask.objects.none()
        return HRTaskService(tenant).list_tasks(
            status=self.request.GET.get("status") or None,
            category=self.request.GET.get("category") or None,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_manage"] = "hr.tasks.manage" in _perms(self.request)
        context["task_next"] = TASK_NEXT
        context["category_choices"] = _choices(HRTask, "category")
        context["status_choices"] = _choices(HRTask, "status")
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "HR Tasks"},
        ]
        return context


@require_http_methods(["POST"])
@login_required
@require_permission("hr.tasks.manage")
def hr_task_create_api(request):
    tenant = _tenant(request)
    try:
        HRTaskService(tenant).create_task(
            title=request.POST.get("title", ""),
            category=request.POST.get("category", "general"),
            due_date=_date(request.POST.get("due_date")),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_tasks(request, tenant))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.tasks.manage")
def hr_task_update_api(request, task_id):
    tenant = _tenant(request)
    get_object_or_404(HRTask, tenant=tenant, id=task_id)
    fields = {k: request.POST[k] for k in ("status", "title", "category") if k in request.POST}
    if request.POST.get("due_date"):
        fields["due_date"] = _date(request.POST["due_date"])
    try:
        HRTaskService(tenant).update_task(task_id, actor=request.user, **fields)
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_tasks(request, tenant))


# ══ Policies ══════════════════════════════════════════════════════════════

def _render_policies(request, tenant):
    active = request.GET.get("active")
    active_flag = None if active in (None, "", "all") else active == "true"
    policies = PolicyService(tenant).list_policies(active=active_flag)
    service = PolicyService(tenant)
    rows = [{"policy": p, "ack": service.ack_summary(p)} for p in policies]
    return render_to_string("core/htmx/hr/policy_list_content.html", {
        "request": request, "rows": rows,
        "can_manage": "hr.settings.manage" in _perms(request),
    })


class PolicyListView(PermissionRequiredMixin, TemplateView):
    required_permissions = ["hr.settings.manage", "hr.employee.view"]
    template_name = "core/hr/ops/policy_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        context["policy_rows_html"] = _render_policies(self.request, tenant)
        context["can_manage"] = "hr.settings.manage" in _perms(self.request)
        context["category_choices"] = _choices(PolicyDocument, "category")
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Policies"},
        ]
        return context


class PolicyAckMatrixView(PermissionRequiredMixin, TemplateView):
    required_permissions = ["hr.settings.manage", "hr.employee.view"]
    template_name = "core/hr/ops/policy_acks.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        policy, rows = PolicyService(tenant).acknowledgement_matrix(kwargs["pk"])
        context["policy"] = policy
        context["rows"] = rows
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Policies", "url": reverse("core:hr_policy_list")},
            {"label": policy.title},
        ]
        return context


@require_http_methods(["POST"])
@login_required
@require_permission("hr.settings.manage")
def policy_create_api(request):
    tenant = _tenant(request)
    try:
        PolicyService(tenant).create_policy(
            title=request.POST.get("title", ""),
            category=request.POST.get("category", "hr"),
            description=request.POST.get("description", ""),
            version=request.POST.get("version", ""),
            effective_date=_date(request.POST.get("effective_date")),
            requires_acknowledgement=request.POST.get("requires_acknowledgement") == "on",
            is_active=True,
            file=request.FILES.get("file"),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_policies(request, tenant))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.settings.manage")
def policy_update_api(request, policy_id):
    tenant = _tenant(request)
    get_object_or_404(PolicyDocument, tenant=tenant, id=policy_id)
    fields = {}
    if "is_active" in request.POST:
        fields["is_active"] = request.POST["is_active"] == "true"
    for key in ("title", "category", "version", "description"):
        if key in request.POST:
            fields[key] = request.POST[key]
    try:
        PolicyService(tenant).update_policy(
            policy_id, actor=request.user, file=request.FILES.get("file"), **fields
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_policies(request, tenant))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.settings.manage")
def policy_delete_api(request, policy_id):
    tenant = _tenant(request)
    get_object_or_404(PolicyDocument, tenant=tenant, id=policy_id)
    try:
        PolicyService(tenant).delete_policy(policy_id, actor=request.user)
    except (NotFoundException, ValidationException) as exc:
        return _err(exc)
    return HttpResponse(_render_policies(request, tenant))


# ══ Audit trail ═══════════════════════════════════════════════════════════

class HRAuditLogView(PermissionRequiredMixin, ListView):
    required_permissions = ["hr.employee.view"]
    template_name = "core/hr/ops/audit_list.html"
    htmx_template_name = "core/htmx/hr/audit_list_content.html"
    context_object_name = "entries"
    paginate_by = 40

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get("HX-Request") == "true"
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return HRAuditLog.objects.none()
        qs = HRAuditLog.objects.filter(tenant=tenant)
        action = self.request.GET.get("action")
        if action:
            qs = qs.filter(action__startswith=action)
        target_id = self.request.GET.get("target_id")
        if target_id:
            qs = qs.filter(target_id=target_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action_prefixes"] = [
            "employee", "contract", "document", "leave", "attendance", "payslip",
            "onboarding", "performance", "training", "exit", "disciplinary",
            "grievance", "vacancy", "applicant", "policy", "task",
        ]
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Audit Trail"},
        ]
        return context
