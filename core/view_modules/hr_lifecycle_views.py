"""HR employee-lifecycle screens for the classic admin: onboarding, employee
exit / offboarding, performance reviews and training records.

Reuses ``core.services.hr_onboarding_service`` / ``hr_exit_service`` /
``hr_performance_service`` / ``hr_training_service`` — the same services the
Next.js HR portal calls. Employee-scoped endpoints return htmx fragments for the
tabs on ``core/hr/employees/detail.html``; the org-wide screens are ListViews.
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
from core.models import (
    Employee, EmployeeExit, ExitClearanceItem, OnboardingChecklist,
    OnboardingItem, PerformanceReview, TrainingRecord,
)
from core.services.exceptions import (
    BusinessLogicException, NotFoundException, ServiceException,
    ValidationException,
)
from core.services.hr_exit_service import ExitService
from core.services.hr_onboarding_service import OnboardingService
from core.services.hr_performance_service import PerformanceService
from core.services.hr_training_service import TrainingService


def _tenant(request):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise Http404("School not found")
    return tenant


def _perms(request):
    return get_permission_set(request.user, getattr(request, "tenant", None))


def _employee_or_404(tenant, employee_id):
    return get_object_or_404(Employee, tenant=tenant, id=employee_id)


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


# ══ Onboarding ═════════════════════════════════════════════════════════════

def _render_onboarding_tab(request, tenant, employee):
    checklist = OnboardingService(tenant).ensure_for_employee(employee)
    return render_to_string("core/htmx/hr/employee_onboarding_tab.html", {
        "request": request, "employee": employee, "checklist": checklist,
        "items": checklist.items.order_by("order"),
        "progress": checklist.progress(), "perms": _perms(request),
    })


@login_required
@require_permission("hr.onboarding.view", "hr.onboarding.manage")
def employee_onboarding_tab(request, employee_id):
    tenant = _tenant(request)
    return HttpResponse(_render_onboarding_tab(request, tenant, _employee_or_404(tenant, employee_id)))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.onboarding.manage")
def onboarding_toggle_item_api(request, item_id):
    tenant = _tenant(request)
    item = get_object_or_404(OnboardingItem, tenant=tenant, id=item_id)
    try:
        OnboardingService(tenant).toggle_item(
            item_id, request.POST.get("is_done") == "true", actor=request.user,
        )
    except (NotFoundException, ServiceException) as exc:
        return _err(exc)
    return HttpResponse(_render_onboarding_tab(request, tenant, item.checklist.employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.onboarding.manage")
def onboarding_add_item_api(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    label = request.POST.get("label", "").strip()
    if not label:
        return _err("A checklist item label is required.")
    try:
        OnboardingService(tenant).add_item(employee_id, label, actor=request.user)
    except (NotFoundException, ServiceException) as exc:
        return _err(exc)
    return HttpResponse(_render_onboarding_tab(request, tenant, employee))


class OnboardingListView(PermissionRequiredMixin, ListView):
    required_permissions = ["hr.onboarding.view", "hr.onboarding.manage"]
    template_name = "core/hr/lifecycle/onboarding_list.html"
    htmx_template_name = "core/htmx/hr/onboarding_list_content.html"
    context_object_name = "checklists"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get("HX-Request") == "true"
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return OnboardingChecklist.objects.none()
        return OnboardingService(tenant).in_progress()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Onboarding"},
        ]
        return context


# ══ Employee exit / offboarding ═══════════════════════════════════════════

def _render_exit_tab(request, tenant, employee):
    exit_row = EmployeeExit.objects.filter(tenant=tenant, employee=employee).first()
    return render_to_string("core/htmx/hr/employee_exit_tab.html", {
        "request": request, "employee": employee, "exit": exit_row,
        "items": exit_row.clearance_items.order_by("order") if exit_row else [],
        "progress": exit_row.clearance_progress() if exit_row else None,
        "exit_type_choices": _choices(EmployeeExit, "exit_type"),
        "payment_choices": _choices(EmployeeExit, "final_payment_status"),
        "perms": _perms(request),
    })


@login_required
@require_permission("hr.exit.view", "hr.exit.manage")
def employee_exit_tab(request, employee_id):
    tenant = _tenant(request)
    return HttpResponse(_render_exit_tab(request, tenant, _employee_or_404(tenant, employee_id)))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.exit.manage")
def exit_start_api(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    try:
        ExitService(tenant).start_exit(
            employee_id=employee_id,
            exit_type=request.POST.get("exit_type", "resignation"),
            notice_date=_date(request.POST.get("notice_date")),
            last_working_date=_date(request.POST.get("last_working_date")),
            reason=request.POST.get("reason", ""),
            actor=request.user,
        )
    except (ValidationException, NotFoundException, BusinessLogicException) as exc:
        return _err(exc)
    return HttpResponse(_render_exit_tab(request, tenant, employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.exit.manage")
def exit_update_api(request, exit_id):
    tenant = _tenant(request)
    exit_row = get_object_or_404(EmployeeExit, tenant=tenant, id=exit_id)
    fields = {
        k: request.POST[k] for k in (
            "final_payment_status", "handover_status", "exit_interview_notes",
            "outstanding_leave_days",
        ) if k in request.POST
    }
    try:
        ExitService(tenant).update_exit(exit_id, actor=request.user, **fields)
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_exit_tab(request, tenant, exit_row.employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.exit.manage")
def exit_toggle_item_api(request, item_id):
    tenant = _tenant(request)
    item = get_object_or_404(ExitClearanceItem, tenant=tenant, id=item_id)
    try:
        ExitService(tenant).toggle_item(
            item_id, request.POST.get("is_done") == "true", actor=request.user,
        )
    except (NotFoundException, ServiceException) as exc:
        return _err(exc)
    return HttpResponse(_render_exit_tab(request, tenant, item.exit.employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.exit.manage")
def exit_complete_api(request, exit_id):
    tenant = _tenant(request)
    exit_row = get_object_or_404(EmployeeExit, tenant=tenant, id=exit_id)
    try:
        ExitService(tenant).complete_exit(exit_id, actor=request.user)
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_exit_tab(request, tenant, exit_row.employee))


class ExitListView(PermissionRequiredMixin, ListView):
    required_permissions = ["hr.exit.view", "hr.exit.manage"]
    template_name = "core/hr/lifecycle/exit_list.html"
    htmx_template_name = "core/htmx/hr/exit_list_content.html"
    context_object_name = "exits"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get("HX-Request") == "true"
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return EmployeeExit.objects.none()
        return ExitService(tenant).list_exits(status=self.request.GET.get("status") or None)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Employee Exit"},
        ]
        context["status_choices"] = ["in_progress", "completed"]
        return context


# ══ Performance reviews ═══════════════════════════════════════════════════

class PerformanceListView(PermissionRequiredMixin, ListView):
    required_permissions = ["hr.performance.view", "hr.performance.conduct"]
    template_name = "core/hr/lifecycle/performance_list.html"
    htmx_template_name = "core/htmx/hr/performance_list_content.html"
    context_object_name = "reviews"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get("HX-Request") == "true"
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return PerformanceReview.objects.none()
        return PerformanceService(tenant).list_reviews(status=self.request.GET.get("status") or None)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            context["employees"] = Employee.objects.filter(
                tenant=tenant, status=True
            ).order_by("first_name", "last_name")
        context["status_choices"] = _choices(PerformanceReview, "status")
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Performance"},
        ]
        return context


class PerformanceDetailView(PermissionRequiredMixin, TemplateView):
    required_permissions = ["hr.performance.view", "hr.performance.conduct"]
    template_name = "core/hr/lifecycle/performance_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        review = get_object_or_404(
            PerformanceReview.objects.select_related("employee", "reviewer"),
            tenant=tenant, id=kwargs["pk"],
        )
        context["review"] = review
        context["criteria"] = review.criteria.order_by("order")
        context["narrative_fields"] = [
            ("objectives", "Objectives", review.objectives or ""),
            ("strengths", "Strengths", review.strengths or ""),
            ("improvement_areas", "Areas for improvement", review.improvement_areas or ""),
            ("development_actions", "Development actions", review.development_actions or ""),
            ("reviewer_comments", "Reviewer comments", review.reviewer_comments or ""),
            ("employee_comments", "Employee comments", review.employee_comments or ""),
        ]
        context["can_conduct"] = "hr.performance.conduct" in _perms(self.request)
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Performance", "url": reverse("core:hr_performance_list")},
            {"label": review.employee.full_name},
        ]
        return context


@require_http_methods(["POST"])
@login_required
@require_permission("hr.performance.conduct")
def review_create_api(request):
    tenant = _tenant(request)
    try:
        review = PerformanceService(tenant).create_review(
            employee_id=request.POST.get("employee_id"),
            review_period=request.POST.get("review_period", ""),
            review_date=_date(request.POST.get("review_date")),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return JsonResponse({"redirect": reverse("core:hr_performance_detail", args=[review.id])})


@require_http_methods(["POST"])
@login_required
@require_permission("hr.performance.conduct")
def review_save_api(request, review_id):
    tenant = _tenant(request)
    narrative = {
        k: request.POST[k] for k in (
            "overall_rating", "objectives", "strengths", "improvement_areas",
            "development_actions", "reviewer_comments", "employee_comments",
            "next_review_date",
        ) if k in request.POST
    }
    if "next_review_date" in narrative:
        narrative["next_review_date"] = _date(narrative["next_review_date"])
    if narrative.get("overall_rating") in ("", None):
        narrative.pop("overall_rating", None)
    try:
        service = PerformanceService(tenant)
        if narrative:
            service.update_review(review_id, actor=request.user, **narrative)
        rows = []
        for key, value in request.POST.items():
            if key.startswith("rating_"):
                rows.append({"id": key[len("rating_"):], "rating": value or None,
                             "comment": request.POST.get(f"comment_{key[len('rating_'):]}", "")})
        if rows:
            service.set_criteria(review_id, rows, actor=request.user)
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return JsonResponse({"ok": True})


@require_http_methods(["POST"])
@login_required
@require_permission("hr.performance.conduct")
def review_complete_api(request, review_id):
    tenant = _tenant(request)
    try:
        PerformanceService(tenant).complete_review(review_id, actor=request.user)
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return JsonResponse({"redirect": reverse("core:hr_performance_detail", args=[review_id])})


@login_required
@require_permission("hr.performance.view", "hr.performance.conduct")
def employee_performance_tab(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    reviews = PerformanceService(tenant).list_reviews(employee_id=employee_id)
    return HttpResponse(render_to_string("core/htmx/hr/employee_performance_tab.html", {
        "request": request, "employee": employee, "reviews": reviews,
    }))


# ══ Training ══════════════════════════════════════════════════════════════

def _render_training_tab(request, tenant, employee):
    records = TrainingService(tenant).list_records(employee_id=employee.id)
    return render_to_string("core/htmx/hr/employee_training_tab.html", {
        "request": request, "employee": employee, "records": records,
        "category_choices": _choices(TrainingRecord, "category"),
        "status_choices": _choices(TrainingRecord, "status"),
        "perms": _perms(request),
    })


@login_required
@require_permission("hr.training.view", "hr.training.manage")
def employee_training_tab(request, employee_id):
    tenant = _tenant(request)
    return HttpResponse(_render_training_tab(request, tenant, _employee_or_404(tenant, employee_id)))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.training.manage")
def training_create_api(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    try:
        TrainingService(tenant).create_record(
            employee_id=employee_id,
            name=request.POST.get("name", ""),
            category=request.POST.get("category", "other"),
            provider=request.POST.get("provider", ""),
            training_date=_date(request.POST.get("training_date")),
            expiry_date=_date(request.POST.get("expiry_date")),
            cost=request.POST.get("cost") or None,
            is_mandatory=request.POST.get("is_mandatory") == "on",
            status=request.POST.get("status", "completed"),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_training_tab(request, tenant, employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.training.manage")
def training_delete_api(request, record_id):
    tenant = _tenant(request)
    record = get_object_or_404(TrainingRecord, tenant=tenant, id=record_id)
    employee = record.employee
    try:
        TrainingService(tenant).delete_record(record_id, actor=request.user)
    except (NotFoundException, ServiceException) as exc:
        return _err(exc)
    return HttpResponse(_render_training_tab(request, tenant, employee))


class TrainingListView(PermissionRequiredMixin, ListView):
    required_permissions = ["hr.training.view", "hr.training.manage"]
    template_name = "core/hr/lifecycle/training_list.html"
    htmx_template_name = "core/htmx/hr/training_list_content.html"
    context_object_name = "records"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get("HX-Request") == "true"
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return TrainingRecord.objects.none()
        return TrainingService(tenant).list_records(
            category=self.request.GET.get("category") or None,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            svc = TrainingService(tenant)
            context["mandatory_gaps"] = svc.mandatory_gaps()
            context["expiring"] = svc.expiring(within_days=60)
        context["category_choices"] = _choices(TrainingRecord, "category")
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Training"},
        ]
        return context
