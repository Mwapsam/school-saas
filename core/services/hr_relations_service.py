"""Employee relations — disciplinary cases and grievances.

Restricted module: every read/write is gated by ``hr.disciplinary.view`` /
``hr.disciplinary.manage`` at the API layer. Every mutation here also writes an
:class:`core.models.HRAuditLog` row via :func:`record_hr_audit`, and closing a
disciplinary case with a warning outcome writes an ``EmploymentHistoryEvent`` so
the employee profile stays the single source of truth.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from core.models import (
    DisciplinaryCase, Employee, EmploymentHistoryEvent, Grievance,
)
from .base import TenantAwareService
from .exceptions import NotFoundException
from .hr_audit import record_hr_audit
from .logging_service import ServiceLogger, logged_operation

_CASE_EDITABLE = {
    "case_type", "severity", "title", "description", "incident_date",
    "status", "investigation_notes", "hearing_date", "outcome",
    "outcome_notes", "action_date", "warning_expiry_date", "appeal_notes",
}
_GRIEVANCE_EDITABLE = {
    "against_id", "category", "title", "description", "date_raised",
    "status", "review_notes", "resolution_notes",
}
_WARNING_OUTCOMES = {"verbal_warning", "written_warning", "final_warning"}


class DisciplinaryService(TenantAwareService[DisciplinaryCase]):
    def __init__(self, tenant):
        super().__init__(DisciplinaryCase, tenant)
        self.logger = ServiceLogger("hr_disciplinary", tenant)

    def list_cases(self, *, status: str = None, employee_id: Any = None):
        qs = self.get_base_queryset().select_related(
            "employee", "employee__employee_department"
        )
        if status:
            qs = qs.filter(status=status)
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        return qs

    def for_employee(self, employee_id: Any):
        return self.list_cases(employee_id=employee_id)

    @logged_operation(action="create", resource_type="disciplinary_case", log_result=True)
    @transaction.atomic
    def create_case(self, *, employee_id: Any, actor=None, **fields) -> DisciplinaryCase:
        try:
            employee = Employee.objects.get(id=employee_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee {employee_id} not found")
        data = {k: v for k, v in fields.items() if k in _CASE_EDITABLE}
        case = self.create(
            employee=employee,
            reported_by_id=getattr(actor, "id", None),
            created_by_id=getattr(actor, "id", None),
            **data,
        )
        record_hr_audit(
            self.tenant, actor=actor, action="disciplinary.create",
            target_type="employee", target_id=employee_id,
            new_value=case.title, detail={"case_type": case.case_type},
        )
        return case

    @logged_operation(action="update", resource_type="disciplinary_case")
    @transaction.atomic
    def update_case(self, case_id: Any, actor=None, **fields) -> DisciplinaryCase:
        case = self.get_by_id(case_id)
        data = {k: v for k, v in fields.items() if k in _CASE_EDITABLE}
        prev_status = case.status
        for key, value in data.items():
            setattr(case, key, value)
        if case.status == "closed" and not case.closed_at:
            case.closed_at = timezone.now()
        if case.status != "closed":
            case.closed_at = None
        case.save()

        if (
            case.status == "closed"
            and prev_status != "closed"
            and case.outcome in _WARNING_OUTCOMES
        ):
            EmploymentHistoryEvent.objects.create(
                tenant=self.tenant,
                employee=case.employee,
                event_type="status_change",
                effective_date=case.action_date or timezone.now().date(),
                new_value={"disciplinary_outcome": case.outcome},
                note=case.title[:500],
                created_by_id=getattr(actor, "id", None),
            )
        record_hr_audit(
            self.tenant, actor=actor, action="disciplinary.update",
            target_type="disciplinary_case", target_id=case_id,
            old_value=prev_status, new_value=case.status,
            detail={"outcome": case.outcome},
        )
        return case


class GrievanceService(TenantAwareService[Grievance]):
    def __init__(self, tenant):
        super().__init__(Grievance, tenant)
        self.logger = ServiceLogger("hr_grievance", tenant)

    def list_grievances(self, *, status: str = None, employee_id: Any = None):
        qs = self.get_base_queryset().select_related("raised_by", "against")
        if status:
            qs = qs.filter(status=status)
        if employee_id:
            qs = qs.filter(raised_by_id=employee_id)
        return qs

    def for_employee(self, employee_id: Any):
        return self.list_grievances(employee_id=employee_id)

    @logged_operation(action="create", resource_type="grievance", log_result=True)
    @transaction.atomic
    def create_grievance(self, *, raised_by_id: Any, actor=None, **fields) -> Grievance:
        try:
            raiser = Employee.objects.get(id=raised_by_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee {raised_by_id} not found")
        data = {k: v for k, v in fields.items() if k in _GRIEVANCE_EDITABLE}
        grievance = self.create(
            raised_by=raiser,
            handled_by_id=getattr(actor, "id", None),
            created_by_id=getattr(actor, "id", None),
            **data,
        )
        record_hr_audit(
            self.tenant, actor=actor, action="grievance.create",
            target_type="employee", target_id=raised_by_id,
            new_value=grievance.title, detail={"category": grievance.category},
        )
        return grievance

    @logged_operation(action="update", resource_type="grievance")
    @transaction.atomic
    def update_grievance(self, grievance_id: Any, actor=None, **fields) -> Grievance:
        grievance = self.get_by_id(grievance_id)
        data = {k: v for k, v in fields.items() if k in _GRIEVANCE_EDITABLE}
        prev_status = grievance.status
        for key, value in data.items():
            setattr(grievance, key, value)
        if grievance.status in ("resolved", "dismissed") and not grievance.resolved_at:
            grievance.resolved_at = timezone.now()
        if grievance.status not in ("resolved", "dismissed"):
            grievance.resolved_at = None
        grievance.save()
        record_hr_audit(
            self.tenant, actor=actor, action="grievance.update",
            target_type="grievance", target_id=grievance_id,
            old_value=prev_status, new_value=grievance.status,
        )
        return grievance
