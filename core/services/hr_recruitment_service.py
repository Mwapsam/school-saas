"""Recruitment / applicant tracking.

``ApplicantService.convert_to_employee`` is the bridge into the rest of HR: it
creates a real :class:`core.models.Employee` from a hired applicant, links the
two, and records an ``employed`` :class:`core.models.EmploymentHistoryEvent`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.models import Applicant, EmploymentHistoryEvent, Vacancy
from .base import TenantAwareService
from .employee_service import EmployeeService
from .exceptions import NotFoundException, ValidationException, BusinessLogicException
from .hr_audit import record_hr_audit
from .logging_service import ServiceLogger, logged_operation


class VacancyService(TenantAwareService[Vacancy]):
    def __init__(self, tenant):
        super().__init__(Vacancy, tenant)
        self.logger = ServiceLogger("hr_vacancy", tenant)

    def list_vacancies(self, *, status: str = None):
        qs = self.get_base_queryset().select_related("department")
        if status:
            qs = qs.filter(status=status)
        return qs

    @logged_operation(action="create", resource_type="vacancy", log_result=True)
    def create_vacancy(self, *, title: str, actor=None, **fields) -> Vacancy:
        if not title.strip():
            raise ValidationException("A vacancy title is required.")
        vacancy = self.create(title=title.strip(), created_by_id=getattr(actor, "id", None), **fields)
        record_hr_audit(
            self.tenant, actor=actor, action="vacancy.create",
            target_type="vacancy", target_id=vacancy.id, new_value=title,
        )
        return vacancy

    @logged_operation(action="update", resource_type="vacancy")
    def update_vacancy(self, vacancy_id: Any, actor=None, **fields) -> Vacancy:
        allowed = {
            "title", "department_id", "number_of_positions", "job_description",
            "employment_type", "is_teaching_role", "date_advertised",
            "closing_date", "status",
        }
        data = {k: v for k, v in fields.items() if k in allowed}
        return self.update(vacancy_id, **data)


class ApplicantService(TenantAwareService[Applicant]):
    def __init__(self, tenant):
        super().__init__(Applicant, tenant)
        self.logger = ServiceLogger("hr_applicant", tenant)

    def list_applicants(self, *, vacancy_id: Any = None, stage: str = None):
        qs = self.get_base_queryset().select_related("vacancy")
        if vacancy_id:
            qs = qs.filter(vacancy_id=vacancy_id)
        if stage:
            qs = qs.filter(stage=stage)
        return qs

    @logged_operation(action="create", resource_type="applicant", log_result=True)
    def create_applicant(self, *, vacancy_id: Any, first_name: str, last_name: str, actor=None, **fields) -> Applicant:
        try:
            vacancy = Vacancy.objects.get(id=vacancy_id, tenant=self.tenant)
        except Vacancy.DoesNotExist:
            raise NotFoundException(f"Vacancy {vacancy_id} not found")
        return self.create(
            vacancy=vacancy,
            first_name=first_name,
            last_name=last_name,
            stage="applied",
            stage_changed_at=timezone.now(),
            created_by_id=getattr(actor, "id", None),
            **fields,
        )

    @logged_operation(action="update", resource_type="applicant")
    def update_applicant(self, applicant_id: Any, actor=None, **fields) -> Applicant:
        allowed = {
            "first_name", "last_name", "email", "phone", "qualifications_summary",
            "interview_date", "interview_panel", "interview_score",
            "interview_comments", "reference_check_notes", "decision_notes",
        }
        data = {k: v for k, v in fields.items() if k in allowed}
        return self.update(applicant_id, **data)

    @logged_operation(action="advance_stage", resource_type="applicant", log_result=True)
    def advance_stage(self, applicant_id: Any, stage: str, actor=None, **fields) -> Applicant:
        valid = {c[0] for c in Applicant.STAGE_CHOICES}
        if stage not in valid:
            raise ValidationException(f"Unknown stage '{stage}'.")
        applicant = self.get_by_id(applicant_id)
        old = applicant.stage
        applicant.stage = stage
        applicant.stage_changed_at = timezone.now()
        for key in ("interview_date", "interview_panel", "interview_score",
                    "interview_comments", "reference_check_notes", "decision_notes"):
            if key in fields and fields[key] is not None:
                setattr(applicant, key, fields[key])
        applicant.save()
        record_hr_audit(
            self.tenant, actor=actor, action="applicant.stage",
            target_type="applicant", target_id=applicant_id,
            field="stage", old_value=old, new_value=stage,
        )
        return applicant

    @logged_operation(action="convert_to_employee", resource_type="applicant", log_result=True)
    @transaction.atomic
    def convert_to_employee(
        self,
        applicant_id: Any,
        *,
        employee_number: str,
        joining_date: date,
        gender: bool,
        actor=None,
        **employee_fields,
    ):
        applicant = self.get_by_id(applicant_id)
        if applicant.converted_employee_id:
            raise BusinessLogicException("This applicant is already an employee.")

        emp_service = EmployeeService(self.tenant)
        employee = emp_service.create_employee(
            employee_number=employee_number,
            first_name=applicant.first_name,
            last_name=applicant.last_name,
            joining_date=joining_date,
            gender=gender,
            email=applicant.email or None,
            mobile_phone=applicant.phone or None,
            is_teaching_staff=applicant.vacancy.is_teaching_role,
            employee_department_id=applicant.vacancy.department_id,
            **employee_fields,
        )

        applicant.converted_employee = employee
        applicant.stage = "hired"
        applicant.stage_changed_at = timezone.now()
        applicant.save(update_fields=["converted_employee", "stage", "stage_changed_at", "updated_at"])

        EmploymentHistoryEvent.objects.create(
            tenant=self.tenant,
            employee=employee,
            event_type="employed",
            effective_date=joining_date,
            new_value={"from_applicant": str(applicant.id), "vacancy": applicant.vacancy.title},
            created_by_id=getattr(actor, "id", None),
        )
        record_hr_audit(
            self.tenant, actor=actor, action="applicant.convert",
            target_type="employee", target_id=employee.id,
            new_value=applicant.full_name,
        )

        # Close the vacancy if every seat is now filled.
        vacancy = applicant.vacancy
        hired = vacancy.applicants.filter(stage="hired").count()
        if hired >= vacancy.number_of_positions and vacancy.status == "open":
            vacancy.status = "filled"
            vacancy.save(update_fields=["status", "updated_at"])

        return employee
