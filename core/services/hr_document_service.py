"""Employee HR documents — upload, list, delete, and expiry reporting."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from core.models import Employee, EmployeeDocument
from .base import TenantAwareService
from .exceptions import NotFoundException
from .hr_audit import record_hr_audit
from .logging_service import ServiceLogger, logged_operation

# Curated list offered in the UI; any string is still accepted.
COMMON_DOCUMENT_TYPES = [
    "NRC / Passport", "CV", "Academic Certificate", "Professional Certificate",
    "Employment Contract", "Job Description", "Reference Letter",
    "Police / Background Clearance", "Signed School Policy", "Other",
]


class EmployeeDocumentService(TenantAwareService[EmployeeDocument]):
    def __init__(self, tenant):
        super().__init__(EmployeeDocument, tenant)
        self.logger = ServiceLogger("hr_document", tenant)

    def for_employee(self, employee_id: Any):
        return self.filter(employee_id=employee_id)

    @logged_operation(action="upload", resource_type="employee_document", log_result=True)
    def add_document(
        self,
        employee_id: Any,
        *,
        document_type: str,
        file,
        expiry_date: date = None,
        issued_date: date = None,
        note: str = "",
        actor=None,
    ) -> EmployeeDocument:
        employee = self._employee(employee_id)
        doc = self.create(
            employee=employee,
            document_type=document_type,
            file=file,
            original_filename=getattr(file, "name", "")[:255],
            issued_date=issued_date,
            expiry_date=expiry_date,
            note=note or "",
            uploaded_by_id=getattr(actor, "id", None),
        )
        record_hr_audit(
            self.tenant, actor=actor, action="document.upload",
            target_type="employee", target_id=employee_id,
            new_value=document_type,
        )
        return doc

    @logged_operation(action="delete", resource_type="employee_document")
    def remove_document(self, document_id: Any, actor=None) -> bool:
        doc = self.get_by_id(document_id)
        employee_id, dtype = doc.employee_id, doc.document_type
        doc.delete()
        record_hr_audit(
            self.tenant, actor=actor, action="document.delete",
            target_type="employee", target_id=employee_id, old_value=dtype,
        )
        return True

    def expiring(self, *, within_days: int = 30, include_expired: bool = True):
        """Documents whose ``expiry_date`` falls inside the window (or is already
        past, when ``include_expired``). Newest-expiring last."""
        today = date.today()
        cutoff = today + timedelta(days=within_days)
        qs = self.get_base_queryset().select_related("employee").filter(
            expiry_date__isnull=False, expiry_date__lte=cutoff
        )
        if not include_expired:
            qs = qs.filter(expiry_date__gte=today)
        return qs.order_by("expiry_date")

    def _employee(self, employee_id: Any) -> Employee:
        try:
            return Employee.objects.get(id=employee_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee {employee_id} not found")
