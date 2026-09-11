"""HR employee-relations screens for the classic admin: disciplinary cases and
grievances. Restricted to users holding ``hr.disciplinary.view`` (read) /
``hr.disciplinary.manage`` (write); every mutation is audit-logged by the
service layer (``core.services.hr_relations_service``).
"""
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from core.authz.access import get_permission_set
from core.authz.mixins import PermissionRequiredMixin, require_permission
from core.models import DisciplinaryCase, Employee, Grievance
from core.services.exceptions import NotFoundException, ValidationException
from core.services.hr_relations_service import DisciplinaryService, GrievanceService


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


def _cases_context(request, tenant):
    return {
        "request": request,
        "cases": DisciplinaryService(tenant).list_cases(
            status=request.GET.get("case_status") or None
        ),
        "can_manage": "hr.disciplinary.manage" in _perms(request),
        "case_type_choices": _choices(DisciplinaryCase, "case_type"),
        "severity_choices": _choices(DisciplinaryCase, "severity"),
        "case_status_choices": _choices(DisciplinaryCase, "status"),
        "outcome_choices": _choices(DisciplinaryCase, "outcome"),
    }


def _grievances_context(request, tenant):
    return {
        "request": request,
        "grievances": GrievanceService(tenant).list_grievances(
            status=request.GET.get("grievance_status") or None
        ),
        "can_manage": "hr.disciplinary.manage" in _perms(request),
        "grievance_category_choices": _choices(Grievance, "category"),
        "grievance_status_choices": _choices(Grievance, "status"),
    }


class RelationsView(PermissionRequiredMixin, TemplateView):
    required_permission = "hr.disciplinary.view"
    template_name = "core/hr/relations/relations.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        context.update(_cases_context(self.request, tenant))
        context.update(_grievances_context(self.request, tenant))
        context["employees"] = Employee.objects.filter(
            tenant=tenant, status=True
        ).order_by("first_name", "last_name")
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Employee Relations"},
        ]
        return context


# ── Disciplinary ─────────────────────────────────────────────────────────

def _render_cases(request, tenant):
    return render_to_string("core/htmx/hr/disciplinary_list_content.html",
                            _cases_context(request, tenant))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.disciplinary.manage")
def disciplinary_create_api(request):
    tenant = _tenant(request)
    if not request.POST.get("title"):
        return _err("A case title is required.")
    try:
        DisciplinaryService(tenant).create_case(
            employee_id=request.POST.get("employee_id"),
            case_type=request.POST.get("case_type", "misconduct"),
            severity=request.POST.get("severity", "minor"),
            title=request.POST["title"].strip(),
            description=request.POST.get("description", ""),
            incident_date=_date(request.POST.get("incident_date")),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_cases(request, tenant))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.disciplinary.manage")
def disciplinary_update_api(request, case_id):
    tenant = _tenant(request)
    get_object_or_404(DisciplinaryCase, tenant=tenant, id=case_id)
    fields = {}
    for key in ("status", "severity", "outcome", "investigation_notes",
                "outcome_notes", "appeal_notes"):
        if key in request.POST:
            fields[key] = request.POST[key]
    for key in ("hearing_date", "action_date", "warning_expiry_date"):
        if request.POST.get(key):
            fields[key] = _date(request.POST[key])
    try:
        DisciplinaryService(tenant).update_case(case_id, actor=request.user, **fields)
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_cases(request, tenant))


# ── Grievances ───────────────────────────────────────────────────────────

def _render_grievances(request, tenant):
    return render_to_string("core/htmx/hr/grievance_list_content.html",
                            _grievances_context(request, tenant))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.disciplinary.manage")
def grievance_create_api(request):
    tenant = _tenant(request)
    if not request.POST.get("title"):
        return _err("A grievance title is required.")
    try:
        GrievanceService(tenant).create_grievance(
            raised_by_id=request.POST.get("raised_by_id"),
            against_id=request.POST.get("against_id") or None,
            category=request.POST.get("category", "other"),
            title=request.POST["title"].strip(),
            description=request.POST.get("description", ""),
            date_raised=_date(request.POST.get("date_raised")),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_grievances(request, tenant))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.disciplinary.manage")
def grievance_update_api(request, grievance_id):
    tenant = _tenant(request)
    get_object_or_404(Grievance, tenant=tenant, id=grievance_id)
    fields = {
        k: request.POST[k] for k in ("status", "review_notes", "resolution_notes")
        if k in request.POST
    }
    try:
        GrievanceService(tenant).update_grievance(grievance_id, actor=request.user, **fields)
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_grievances(request, tenant))


# ── Employee-detail tab ──────────────────────────────────────────────────

@login_required
@require_permission("hr.disciplinary.view")
def employee_disciplinary_tab(request, employee_id):
    tenant = _tenant(request)
    employee = get_object_or_404(Employee, tenant=tenant, id=employee_id)
    return HttpResponse(render_to_string("core/htmx/hr/employee_disciplinary_tab.html", {
        "request": request,
        "employee": employee,
        "cases": DisciplinaryService(tenant).for_employee(employee_id),
        "grievances": GrievanceService(tenant).for_employee(employee_id),
    }))
