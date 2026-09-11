"""HR employee-record screens for the classic admin: contracts, documents,
qualifications and employment history.

These reuse the same service layer as the Next.js HR portal
(``core.services.hr_contract_service`` / ``hr_document_service``) so the two
front-ends stay behaviourally identical. The employee-scoped endpoints render
htmx fragments swapped into the tabs on ``core/hr/employees/detail.html``; the
org-wide contract screen is a normal paginated ListView.
"""
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView

from core.authz.mixins import PermissionRequiredMixin, require_permission
from core.models import (
    Employee, EmployeeContract, EmployeeDocument, EmployeeQualification,
    EmploymentHistoryEvent,
)
from core.services.exceptions import (
    NotFoundException, ServiceException, ValidationException,
)
from core.services.hr_contract_service import ContractService
from core.services.hr_document_service import EmployeeDocumentService

CONTRACT_TYPE_CHOICES = [
    ("permanent", "Permanent"), ("fixed_term", "Fixed Term"),
    ("probation", "Probation"), ("temporary", "Temporary"),
    ("casual", "Casual"), ("consultant", "Consultant / Contract"),
    ("intern", "Internship"),
]
QUALIFICATION_TYPE_CHOICES = [
    ("academic", "Academic"), ("teaching", "Teaching"),
    ("professional", "Professional"), ("other", "Other"),
]
CONTRACT_DECISIONS = {"renewal_pending", "not_renewed", "active"}


def _tenant(request):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        raise Http404("School not found")
    return tenant


def _employee_or_404(tenant, employee_id):
    return get_object_or_404(Employee, tenant=tenant, id=employee_id)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationException("Dates must be in YYYY-MM-DD format.")


# ── Contracts: employee tab ──────────────────────────────────────────────

def _render_contracts_tab(request, tenant, employee):
    contracts = ContractService(tenant).for_employee(employee.id)
    return render_to_string(
        "core/htmx/hr/employee_contracts_tab.html",
        {
            "request": request,
            "employee": employee,
            "contracts": contracts,
            "contract_type_choices": CONTRACT_TYPE_CHOICES,
            "perms": getattr(request, "perms", None) or _perms(request),
        },
    )


def _perms(request):
    from core.authz.access import get_permission_set

    return get_permission_set(request.user, getattr(request, "tenant", None))


@login_required
@require_permission("hr.contract.view")
def employee_contracts_tab(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    return HttpResponse(_render_contracts_tab(request, tenant, employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.contract.manage")
def contract_create_api(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    try:
        ContractService(tenant).create_contract(
            employee.id,
            contract_type=request.POST.get("contract_type", "fixed_term"),
            start_date=_parse_date(request.POST.get("start_date")),
            end_date=_parse_date(request.POST.get("end_date")),
            probation_end_date=_parse_date(request.POST.get("probation_end_date")),
            salary_review_date=_parse_date(request.POST.get("salary_review_date")),
            notes=request.POST.get("notes", ""),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return JsonResponse({"error": str(exc.message)}, status=400)
    return HttpResponse(_render_contracts_tab(request, tenant, employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.contract.manage")
def contract_renew_api(request, contract_id):
    tenant = _tenant(request)
    contract = get_object_or_404(EmployeeContract, tenant=tenant, id=contract_id)
    try:
        ContractService(tenant).renew(
            contract_id,
            new_start_date=_parse_date(request.POST.get("new_start_date")),
            new_end_date=_parse_date(request.POST.get("new_end_date")),
            contract_type=request.POST.get("contract_type") or None,
            notes=request.POST.get("notes", ""),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return JsonResponse({"error": str(exc.message)}, status=400)
    return HttpResponse(_render_contracts_tab(request, tenant, contract.employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.contract.manage")
def contract_decision_api(request, contract_id):
    tenant = _tenant(request)
    contract = get_object_or_404(EmployeeContract, tenant=tenant, id=contract_id)
    decision = request.POST.get("decision", "")
    if decision not in CONTRACT_DECISIONS:
        return JsonResponse({"error": "Unknown decision."}, status=400)
    try:
        ContractService(tenant).set_decision(contract_id, decision, actor=request.user)
    except (ValidationException, NotFoundException) as exc:
        return JsonResponse({"error": str(exc.message)}, status=400)
    return HttpResponse(_render_contracts_tab(request, tenant, contract.employee))


# ── Contracts: org-wide screen ──────────────────────────────────────────

class ContractOrgListView(PermissionRequiredMixin, ListView):
    required_permission = "hr.contract.view"
    template_name = "core/hr/records/contract_list.html"
    htmx_template_name = "core/htmx/hr/contract_list_content.html"
    context_object_name = "contracts"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get("HX-Request") == "true"
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        if not tenant:
            return EmployeeContract.objects.none()
        status = self.request.GET.get("status") or None
        return ContractService(tenant).org_table(status=status)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["back_url"] = reverse("core:hr_dashboard")
        context["crumbs"] = [
            {"label": "HR", "url": reverse("core:hr_dashboard")},
            {"label": "Contracts"},
        ]
        context["status_choices"] = [
            "active", "expiring_soon", "renewal_pending", "renewed",
            "not_renewed", "expired",
        ]
        return context


# ── Documents: employee tab ─────────────────────────────────────────────

def _render_documents_tab(request, tenant, employee):
    documents = EmployeeDocumentService(tenant).for_employee(employee.id)
    return render_to_string(
        "core/htmx/hr/employee_documents_tab.html",
        {
            "request": request,
            "employee": employee,
            "documents": documents,
            "perms": _perms(request),
        },
    )


@login_required
@require_permission("hr.document.view")
def employee_documents_tab(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    return HttpResponse(_render_documents_tab(request, tenant, employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.document.manage")
def document_upload_api(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "A file is required."}, status=400)
    try:
        EmployeeDocumentService(tenant).add_document(
            employee.id,
            document_type=request.POST.get("document_type", "").strip() or "Other",
            file=upload,
            expiry_date=_parse_date(request.POST.get("expiry_date")),
            issued_date=_parse_date(request.POST.get("issued_date")),
            note=request.POST.get("note", ""),
            actor=request.user,
        )
    except (ValidationException, NotFoundException) as exc:
        return JsonResponse({"error": str(exc.message)}, status=400)
    return HttpResponse(_render_documents_tab(request, tenant, employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.document.manage")
def document_delete_api(request, document_id):
    tenant = _tenant(request)
    document = get_object_or_404(EmployeeDocument, tenant=tenant, id=document_id)
    employee = document.employee
    try:
        EmployeeDocumentService(tenant).remove_document(document_id, actor=request.user)
    except (NotFoundException, ServiceException) as exc:
        return JsonResponse({"error": str(exc.message)}, status=400)
    return HttpResponse(_render_documents_tab(request, tenant, employee))


# ── Qualifications: employee tab ────────────────────────────────────────

def _render_qualifications_tab(request, tenant, employee):
    qualifications = EmployeeQualification.objects.filter(
        tenant=tenant, employee=employee
    ).order_by("-is_highest", "-year_obtained")
    return render_to_string(
        "core/htmx/hr/employee_qualifications_tab.html",
        {
            "request": request,
            "employee": employee,
            "qualifications": qualifications,
            "qualification_type_choices": QUALIFICATION_TYPE_CHOICES,
            "perms": _perms(request),
        },
    )


@login_required
@require_permission("hr.employee.view")
def employee_qualifications_tab(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    return HttpResponse(_render_qualifications_tab(request, tenant, employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.employee.manage")
def qualification_add_api(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "A qualification name is required."}, status=400)
    year = request.POST.get("year_obtained")
    is_highest = request.POST.get("is_highest") == "on"
    if is_highest:
        EmployeeQualification.objects.filter(
            tenant=tenant, employee=employee, is_highest=True
        ).update(is_highest=False)
    EmployeeQualification.objects.create(
        tenant=tenant,
        employee=employee,
        qualification_type=request.POST.get("qualification_type", "academic"),
        name=name,
        institution=request.POST.get("institution", "").strip(),
        year_obtained=int(year) if year else None,
        is_highest=is_highest,
    )
    return HttpResponse(_render_qualifications_tab(request, tenant, employee))


@require_http_methods(["POST"])
@login_required
@require_permission("hr.employee.manage")
def qualification_delete_api(request, qualification_id):
    tenant = _tenant(request)
    qualification = get_object_or_404(
        EmployeeQualification, tenant=tenant, id=qualification_id
    )
    employee = qualification.employee
    qualification.delete()
    return HttpResponse(_render_qualifications_tab(request, tenant, employee))


# ── Employment history: read-only employee tab ─────────────────────────

@login_required
@require_permission("hr.employee.view")
def employee_history_tab(request, employee_id):
    tenant = _tenant(request)
    employee = _employee_or_404(tenant, employee_id)
    events = EmploymentHistoryEvent.objects.filter(
        tenant=tenant, employee=employee
    ).order_by("-effective_date", "-created_at")
    return HttpResponse(render_to_string(
        "core/htmx/hr/employee_history_tab.html",
        {"request": request, "employee": employee, "events": events},
    ))
