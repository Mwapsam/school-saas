"""Staff training / CPD records and mandatory-training compliance."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db.models import Q

from core.models import Employee, TrainingRecord
from .base import TenantAwareService
from .exceptions import NotFoundException, ValidationException
from .hr_audit import record_hr_audit
from .logging_service import ServiceLogger, logged_operation

_EDITABLE = {
    "name", "category", "provider", "training_date", "cost", "expiry_date",
    "status", "is_mandatory", "notes",
}


class TrainingService(TenantAwareService[TrainingRecord]):
    def __init__(self, tenant):
        super().__init__(TrainingRecord, tenant)
        self.logger = ServiceLogger("hr_training", tenant)

    def list_records(self, *, employee_id: Any = None, category: str = None, status: str = None):
        qs = self.get_base_queryset().select_related("employee")
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if category:
            qs = qs.filter(category=category)
        if status:
            qs = qs.filter(status=status)
        return qs

    @logged_operation(action="create", resource_type="training_record", log_result=True)
    def create_record(self, *, employee_id: Any, name: str, actor=None, **fields) -> TrainingRecord:
        try:
            employee = Employee.objects.get(id=employee_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee {employee_id} not found")
        if not name.strip():
            raise ValidationException("A training name is required.")
        data = {k: v for k, v in fields.items() if k in _EDITABLE}
        record = self.create(
            employee=employee, name=name.strip(),
            created_by_id=getattr(actor, "id", None), **data,
        )
        record_hr_audit(
            self.tenant, actor=actor, action="training.create",
            target_type="employee", target_id=employee_id, new_value=name,
        )
        return record

    @logged_operation(action="update", resource_type="training_record")
    def update_record(self, record_id: Any, actor=None, **fields) -> TrainingRecord:
        data = {k: v for k, v in fields.items() if k in _EDITABLE}
        return self.update(record_id, **data)

    @logged_operation(action="delete", resource_type="training_record")
    def delete_record(self, record_id: Any, actor=None) -> bool:
        record = self.get_by_id(record_id)
        emp_id = record.employee_id
        record.delete()
        record_hr_audit(
            self.tenant, actor=actor, action="training.delete",
            target_type="employee", target_id=emp_id,
        )
        return True

    def expiring(self, *, within_days: int = 60, mandatory_only: bool = False):
        today = date.today()
        cutoff = today + timedelta(days=within_days)
        qs = self.get_base_queryset().select_related("employee").filter(
            status="completed", expiry_date__isnull=False, expiry_date__lte=cutoff
        )
        if mandatory_only:
            qs = qs.filter(is_mandatory=True)
        return qs.order_by("expiry_date")

    def mandatory_gaps(self):
        """Active employees with no current (completed, non-expired) record in
        each mandatory category. Returns ``[{employee, missing: [category,...]}]``."""
        today = date.today()
        current = TrainingRecord.objects.filter(
            tenant=self.tenant,
            status="completed",
            category__in=TrainingRecord.MANDATORY_CATEGORIES,
        ).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))

        have: dict = {}
        for emp_id, cat in current.values_list("employee_id", "category"):
            have.setdefault(emp_id, set()).add(cat)

        rows = []
        employees = Employee.objects.filter(tenant=self.tenant, status=True).only(
            "id", "first_name", "last_name", "employee_number"
        )
        for emp in employees:
            missing = [c for c in TrainingRecord.MANDATORY_CATEGORIES if c not in have.get(emp.id, set())]
            if missing:
                rows.append({
                    "id": str(emp.id),
                    "name": emp.full_name,
                    "employee_number": emp.employee_number,
                    "missing": missing,
                })
        return rows
