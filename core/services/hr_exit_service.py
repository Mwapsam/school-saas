"""Employee exit / offboarding.

``complete_exit`` is the terminal step: it requires every clearance item ticked,
then flips the employee to ``exited`` (and inactive), writes an ``exit``
:class:`core.models.EmploymentHistoryEvent`, and snapshots an
:class:`core.models.ArchivedEmployee`. The ``Employee`` row is kept.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from core.models import (
    ArchivedEmployee, Employee, EmployeeExit, ExitClearanceItem,
    EmploymentHistoryEvent,
)
from .base import TenantAwareService
from .exceptions import BusinessLogicException, NotFoundException, ValidationException
from .hr_audit import record_hr_audit
from .logging_service import ServiceLogger, logged_operation

_EDITABLE = {
    "exit_type", "notice_date", "last_working_date", "reason",
    "exit_interview_notes", "final_payment_status", "outstanding_leave_days",
    "handover_status",
}


class ExitService(TenantAwareService[EmployeeExit]):
    def __init__(self, tenant):
        super().__init__(EmployeeExit, tenant)
        self.logger = ServiceLogger("hr_exit", tenant)

    def list_exits(self, *, status: str = None):
        qs = self.get_base_queryset().select_related(
            "employee", "employee__employee_department"
        ).prefetch_related("clearance_items")
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_for_employee(self, employee_id: Any) -> EmployeeExit:
        exit_row = EmployeeExit.objects.filter(
            tenant=self.tenant, employee_id=employee_id
        ).prefetch_related("clearance_items").first()
        if not exit_row:
            raise NotFoundException("No exit record for this employee.")
        return exit_row

    @logged_operation(action="start", resource_type="employee_exit", log_result=True)
    @transaction.atomic
    def start_exit(
        self,
        *,
        employee_id: Any,
        exit_type: str,
        notice_date: date = None,
        last_working_date: date = None,
        reason: str = "",
        actor=None,
    ) -> EmployeeExit:
        try:
            employee = Employee.objects.get(id=employee_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee {employee_id} not found")
        if EmployeeExit.objects.filter(tenant=self.tenant, employee=employee).exists():
            raise BusinessLogicException("This employee already has an exit record.")

        exit_row = self.create(
            employee=employee,
            exit_type=exit_type,
            notice_date=notice_date,
            last_working_date=last_working_date,
            reason=reason or "",
            created_by_id=getattr(actor, "id", None),
        )
        ExitClearanceItem.objects.bulk_create([
            ExitClearanceItem(tenant=self.tenant, exit=exit_row, label=label, order=i)
            for i, label in enumerate(EmployeeExit.DEFAULT_CLEARANCE_ITEMS)
        ])

        if employee.employment_status not in ("exited",):
            employee.employment_status = "notice_period"
            employee.save(update_fields=["employment_status", "updated_at"])

        record_hr_audit(
            self.tenant, actor=actor, action="exit.start",
            target_type="employee", target_id=employee_id, new_value=exit_type,
        )
        return exit_row

    @logged_operation(action="update", resource_type="employee_exit")
    def update_exit(self, exit_id: Any, actor=None, **fields) -> EmployeeExit:
        data = {k: v for k, v in fields.items() if k in _EDITABLE}
        return self.update(exit_id, **data)

    @logged_operation(action="toggle_item", resource_type="exit_clearance_item")
    def toggle_item(self, item_id: Any, is_done: bool, actor=None, note: str = None) -> ExitClearanceItem:
        try:
            item = ExitClearanceItem.objects.select_related("exit").get(
                id=item_id, tenant=self.tenant
            )
        except ExitClearanceItem.DoesNotExist:
            raise NotFoundException(f"Clearance item {item_id} not found")
        item.is_done = is_done
        item.done_at = timezone.now() if is_done else None
        item.done_by_id = getattr(actor, "id", None) if is_done else None
        if note is not None:
            item.note = note
        item.save()
        return item

    @logged_operation(action="complete", resource_type="employee_exit", log_result=True)
    @transaction.atomic
    def complete_exit(self, exit_id: Any, actor=None) -> EmployeeExit:
        exit_row = self.get_by_id(exit_id)
        progress = exit_row.clearance_progress()
        if progress["total"] and progress["done"] < progress["total"]:
            raise ValidationException(
                "All clearance items must be completed before finalising the exit."
            )

        employee = exit_row.employee
        leaving = exit_row.last_working_date or date.today()

        exit_row.status = "completed"
        exit_row.completed_at = timezone.now()
        exit_row.save(update_fields=["status", "completed_at", "updated_at"])

        employee.employment_status = "exited"
        employee.status = False
        employee.save(update_fields=["employment_status", "status", "updated_at"])

        EmploymentHistoryEvent.objects.create(
            tenant=self.tenant,
            employee=employee,
            event_type="exit",
            effective_date=leaving,
            new_value={"exit_type": exit_row.exit_type},
            note=exit_row.reason[:500],
            created_by_id=getattr(actor, "id", None),
        )
        ArchivedEmployee.objects.get_or_create(
            tenant=self.tenant,
            former_id=str(employee.id),
            defaults={
                "employee_number": employee.employee_number,
                "first_name": employee.first_name,
                "middle_name": employee.middle_name,
                "last_name": employee.last_name,
                "employee_department_name": getattr(employee.employee_department, "name", None),
                "employee_category_name": getattr(employee.employee_category, "name", None),
                "status_description": exit_row.get_exit_type_display(),
                "date_of_leaving": leaving,
            },
        )
        record_hr_audit(
            self.tenant, actor=actor, action="exit.complete",
            target_type="employee", target_id=employee.id,
            new_value=exit_row.exit_type,
        )
        return exit_row
