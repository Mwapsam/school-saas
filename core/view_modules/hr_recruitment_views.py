"""HR recruitment screens for the classic admin: vacancies and the applicant
pipeline, including convert-to-employee.

Reuses ``core.services.hr_recruitment_service`` (``VacancyService`` /
``ApplicantService``) — the same services the Next.js HR portal calls.
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
from core.models import Applicant, EmployeeDepartment, Vacancy
from core.services.exceptions import (
    BusinessLogicException, NotFoundException, ValidationException,
)
from core.services.hr_recruitment_service import ApplicantService, VacancyService

STAGE_ORDER = [
    "applied", "shortlisted", "interview", "reference_check", "offered",
    "hired", "unsuccessful",
]


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


# ── Vacancies ────────────────────────────────────────────────────────────

class VacancyListView(PermissionRequiredMixin, ListView):
    required_permissions = ["hr.recruitment.view", "hr.recruitment.manage"]
    template_name = "core/hr/recruitment/vacancy_list.html"
    htmx_template_name = "core/htmx/hr/vacancy_list_content.html"
    context_object_name = "vacancies"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get("HX-Request") == "true"
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return Vacancy.objects.none()
        return VacancyService(tenant).list_vacancies(
            status=self.request.GET.get("status") or None
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            context["departments"] = EmployeeDepartment.objects.filter(
                tenant=tenant, status=True
            ).order_by("name")
        context["employment_type_choices"] = _choices(Vacancy, "employment_type")
        context["status_choices"] = _choices(Vacancy, "status")
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Recruitment"},
        ]
        return context


class VacancyDetailView(PermissionRequiredMixin, TemplateView):
    required_permissions = ["hr.recruitment.view", "hr.recruitment.manage"]
    template_name = "core/hr/recruitment/vacancy_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = _tenant(self.request)
        vacancy = get_object_or_404(
            Vacancy.objects.select_related("department"), tenant=tenant, id=kwargs["pk"]
        )
        applicants = ApplicantService(tenant).list_applicants(vacancy_id=vacancy.id)
        by_stage = {stage: [] for stage in STAGE_ORDER}
        for applicant in applicants:
            by_stage.setdefault(applicant.stage, []).append(applicant)
        context["vacancy"] = vacancy
        context["stage_groups"] = [(s, by_stage.get(s, [])) for s in STAGE_ORDER]
        context["stage_choices"] = Applicant.STAGE_CHOICES
        context["can_manage"] = "hr.recruitment.manage" in _perms(self.request)
        context["can_convert"] = "hr.employee.manage" in _perms(self.request)
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Recruitment", "url": reverse("core:hr_vacancy_list")},
            {"label": vacancy.title},
        ]
        return context


@require_http_methods(["POST"])
@login_required
@require_permission("hr.recruitment.manage")
def vacancy_create_api(request):
    tenant = _tenant(request)
    try:
        vacancy = VacancyService(tenant).create_vacancy(
            title=request.POST.get("title", ""),
            department_id=request.POST.get("department_id") or None,
            number_of_positions=int(request.POST.get("number_of_positions") or 1),
            employment_type=request.POST.get("employment_type", "full_time"),
            is_teaching_role=request.POST.get("is_teaching_role") == "on",
            job_description=request.POST.get("job_description", ""),
            closing_date=_date(request.POST.get("closing_date")),
            status=request.POST.get("status", "open"),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return JsonResponse({"redirect": reverse("core:hr_vacancy_detail", args=[vacancy.id])})


@require_http_methods(["POST"])
@login_required
@require_permission("hr.recruitment.manage")
def vacancy_update_api(request, vacancy_id):
    tenant = _tenant(request)
    fields = {k: request.POST[k] for k in ("status", "title", "job_description",
                                           "number_of_positions") if k in request.POST}
    try:
        VacancyService(tenant).update_vacancy(vacancy_id, actor=request.user, **fields)
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return JsonResponse({"ok": True})


# ── Applicants ───────────────────────────────────────────────────────────

def _render_pipeline(request, tenant, vacancy):
    applicants = ApplicantService(tenant).list_applicants(vacancy_id=vacancy.id)
    by_stage = {}
    for applicant in applicants:
        by_stage.setdefault(applicant.stage, []).append(applicant)
    return render_to_string("core/htmx/hr/applicant_pipeline.html", {
        "request": request,
        "vacancy": vacancy,
        "stage_groups": [(s, by_stage.get(s, [])) for s in STAGE_ORDER],
        "stage_choices": Applicant.STAGE_CHOICES,
        "can_manage": "hr.recruitment.manage" in _perms(request),
        "can_convert": "hr.employee.manage" in _perms(request),
    })


@require_http_methods(["POST"])
@login_required
@require_permission("hr.recruitment.manage")
def applicant_create_api(request, vacancy_id):
    tenant = _tenant(request)
    vacancy = get_object_or_404(Vacancy, tenant=tenant, id=vacancy_id)
    if not request.POST.get("first_name") or not request.POST.get("last_name"):
        return _err("First and last name are required.")
    try:
        ApplicantService(tenant).create_applicant(
            vacancy_id=vacancy_id,
            first_name=request.POST["first_name"].strip(),
            last_name=request.POST["last_name"].strip(),
            email=request.POST.get("email", ""),
            phone=request.POST.get("phone", ""),
            qualifications_summary=request.POST.get("qualifications_summary", ""),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_pipeline(request, tenant, vacancy))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.recruitment.manage")
def applicant_advance_api(request, applicant_id):
    tenant = _tenant(request)
    applicant = get_object_or_404(
        Applicant.objects.select_related("vacancy"), tenant=tenant, id=applicant_id
    )
    extra = {}
    for key in ("interview_date", "interview_panel", "interview_score",
                "interview_comments", "reference_check_notes", "decision_notes"):
        if request.POST.get(key):
            extra[key] = _date(request.POST[key]) if key == "interview_date" else request.POST[key]
    try:
        ApplicantService(tenant).advance_stage(
            applicant_id, request.POST.get("stage", ""), actor=request.user, **extra
        )
    except (ValidationException, NotFoundException) as exc:
        return _err(exc)
    return HttpResponse(_render_pipeline(request, tenant, applicant.vacancy))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.employee.manage")
def applicant_convert_api(request, applicant_id):
    tenant = _tenant(request)
    applicant = get_object_or_404(
        Applicant.objects.select_related("vacancy"), tenant=tenant, id=applicant_id
    )
    try:
        result = ApplicantService(tenant).convert_to_employee(
            applicant_id,
            employee_number=request.POST.get("employee_number", "").strip(),
            joining_date=_date(request.POST.get("joining_date")),
            gender=request.POST.get("gender", "true") == "true",
            actor=request.user,
        )
    except (ValidationException, NotFoundException, BusinessLogicException) as exc:
        return _err(exc)
    employee = result[0] if isinstance(result, tuple) else result
    return JsonResponse({"redirect": reverse("core:employee_detail", args=[employee.id])})
