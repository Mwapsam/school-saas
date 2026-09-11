"""Employee contract lifecycle.

Renewals never mutate a past contract: :meth:`renew` closes the current one
(``renewal_status='renewed'``) and creates a fresh row that ``supersedes`` it,
so the employee's contract history is complete and append-only.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from django.db import transaction

from core.models import Employee, EmployeeContract, EmploymentHistoryEvent
from .base import TenantAwareService
from .exceptions import NotFoundException, ValidationException
from .hr_audit import record_hr_audit
from .logging_service import ServiceLogger, logged_operation

# Windows (days) at which a dated contract is considered "expiring soon".
EXPIRY_WINDOWS = (90, 60, 30)


class ContractService(TenantAwareService[EmployeeContract]):
    def __init__(self, tenant):
        super().__init__(EmployeeContract, tenant)
        self.logger = ServiceLogger("hr_contract", tenant)

    # ── reads ────────────────────────────────────────────────────────────
    def for_employee(self, employee_id: Any):
        return self.filter(employee_id=employee_id).select_related("employee")

    def current_for_employee(self, employee_id: Any) -> Optional[EmployeeContract]:
        return self.for_employee(employee_id).order_by("-start_date", "-created_at").first()

    def org_table(self, *, status: str = None, expiring_within: int = None):
        """All contracts, newest first, optionally filtered. Callers read
        ``days_remaining`` off each row."""
        qs = self.get_base_queryset().select_related(
            "employee", "employee__employee_position", "employee__employee_department"
        )
        if status:
            qs = qs.filter(renewal_status=status)
        if expiring_within is not None:
            cutoff = date.today() + timedelta(days=expiring_within)
            qs = qs.filter(end_date__isnull=False, end_date__lte=cutoff, end_date__gte=date.today())
        return qs.order_by("end_date", "-start_date")

    # ── writes ───────────────────────────────────────────────────────────
    @logged_operation(action="create", resource_type="employee_contract", log_result=True)
    def create_contract(
        self,
        employee_id: Any,
        contract_type: str,
        start_date: date,
        end_date: date = None,
        probation_end_date: date = None,
        salary_review_date: date = None,
        notes: str = "",
        actor=None,
        **extra,
    ) -> EmployeeContract:
        employee = self._employee(employee_id)
        if end_date and end_date < start_date:
            raise ValidationException("Contract end date cannot be before its start date.")

        contract = self.create(
            employee=employee,
            contract_type=contract_type,
            start_date=start_date,
            end_date=end_date,
            probation_end_date=probation_end_date,
            salary_review_date=salary_review_date,
            notes=notes or "",
            renewal_status=self._status_for(end_date),
            created_by_id=getattr(actor, "id", None),
            **extra,
        )
        record_hr_audit(
            self.tenant, actor=actor, action="contract.create",
            target_type="employee", target_id=employee_id,
            new_value=f"{contract_type} {start_date}..{end_date or 'open'}",
        )
        return contract

    @logged_operation(action="renew", resource_type="employee_contract", log_result=True)
    @transaction.atomic
    def renew(
        self,
        contract_id: Any,
        *,
        new_start_date: date,
        new_end_date: date = None,
        contract_type: str = None,
        notes: str = "",
        actor=None,
    ) -> EmployeeContract:
        old = self.get_by_id(contract_id)
        old.renewal_status = "renewed"
        old.save(update_fields=["renewal_status", "updated_at"])

        fresh = self.create(
            employee=old.employee,
            contract_type=contract_type or old.contract_type,
            start_date=new_start_date,
            end_date=new_end_date,
            salary_review_date=old.salary_review_date,
            notes=notes or "",
            renewal_status=self._status_for(new_end_date),
            supersedes=old,
            created_by_id=getattr(actor, "id", None),
        )
        EmploymentHistoryEvent.objects.create(
            tenant=self.tenant,
            employee=old.employee,
            event_type="contract_renewal",
            effective_date=new_start_date,
            old_value={"end_date": str(old.end_date) if old.end_date else None,
                       "type": old.contract_type},
            new_value={"end_date": str(new_end_date) if new_end_date else None,
                       "type": fresh.contract_type},
            note=notes or "",
            created_by_id=getattr(actor, "id", None),
        )
        record_hr_audit(
            self.tenant, actor=actor, action="contract.renew",
            target_type="employee", target_id=old.employee_id,
            old_value=str(old.end_date), new_value=str(new_end_date),
        )
        return fresh

    @logged_operation(action="decision", resource_type="employee_contract")
    def set_decision(self, contract_id: Any, decision: str, actor=None) -> EmployeeContract:
        """decision ∈ {renewal_pending, not_renewed, expiring_soon, active}."""
        valid = {"renewal_pending", "not_renewed", "expiring_soon", "active"}
        if decision not in valid:
            raise ValidationException(f"Unknown contract decision '{decision}'.")
        contract = self.get_by_id(contract_id)
        old = contract.renewal_status
        contract.renewal_status = decision
        contract.save(update_fields=["renewal_status", "updated_at"])
        record_hr_audit(
            self.tenant, actor=actor, action="contract.decision",
            target_type="contract", target_id=contract_id,
            field="renewal_status", old_value=old, new_value=decision,
        )
        return contract

    def refresh_statuses(self) -> int:
        """Recompute ``renewal_status`` for every dated contract that HR has not
        manually pinned (renewed / renewal_pending / not_renewed). Returns the
        number of rows changed. Safe to call from the nightly job."""
        pinned = {"renewed", "renewal_pending", "not_renewed"}
        changed = 0
        qs = self.get_base_queryset().filter(end_date__isnull=False).exclude(
            renewal_status__in=pinned
        )
        for contract in qs:
            want = self._status_for(contract.end_date)
            if want != contract.renewal_status:
                contract.renewal_status = want
                contract.save(update_fields=["renewal_status", "updated_at"])
                changed += 1
        return changed

    # ── helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _status_for(end_date: Optional[date]) -> str:
        if not end_date:
            return "active"
        remaining = (end_date - date.today()).days
        if remaining < 0:
            return "expired"
        if remaining <= EXPIRY_WINDOWS[0]:
            return "expiring_soon"
        return "active"

    def _employee(self, employee_id: Any) -> Employee:
        try:
            return Employee.objects.get(id=employee_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee {employee_id} not found")
