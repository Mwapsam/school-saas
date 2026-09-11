"""Policy library + staff acknowledgements.

HR publishes :class:`core.models.PolicyDocument` rows; each active policy that
``requires_acknowledgement`` shows up as outstanding for every active employee
until they record a :class:`core.models.PolicyAcknowledgement`.
"""
from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from core.models import Employee, PolicyAcknowledgement, PolicyDocument
from .base import TenantAwareService
from .exceptions import NotFoundException, ValidationException
from .hr_audit import record_hr_audit
from .logging_service import ServiceLogger, logged_operation

_EDITABLE = {
    "title", "category", "description", "version", "effective_date",
    "requires_acknowledgement", "is_active",
}


class PolicyService(TenantAwareService[PolicyDocument]):
    def __init__(self, tenant):
        super().__init__(PolicyDocument, tenant)
        self.logger = ServiceLogger("hr_policy", tenant)

    # ── reads ────────────────────────────────────────────────────────────
    def list_policies(self, *, active: bool = None, category: str = None):
        qs = self.get_base_queryset()
        if active is not None:
            qs = qs.filter(is_active=active)
        if category:
            qs = qs.filter(category=category)
        return qs

    def _active_employee_count(self) -> int:
        return Employee.objects.filter(tenant=self.tenant, status=True).count()

    def ack_summary(self, policy: PolicyDocument) -> dict:
        total = self._active_employee_count()
        done = PolicyAcknowledgement.objects.filter(
            tenant=self.tenant, policy=policy, employee__status=True
        ).count()
        return {
            "acknowledged": done,
            "eligible": total,
            "percent": round(done / total * 100) if total else 0,
        }

    def acknowledgement_matrix(self, policy_id: Any):
        policy = self.get_by_id(policy_id)
        acked = {
            a.employee_id: a.acknowledged_at
            for a in PolicyAcknowledgement.objects.filter(
                tenant=self.tenant, policy=policy
            )
        }
        rows = []
        for e in Employee.objects.filter(
            tenant=self.tenant, status=True
        ).order_by("first_name", "last_name"):
            rows.append({
                "employee_id": str(e.id),
                "name": e.full_name,
                "employee_number": e.employee_number,
                "department": getattr(e.employee_department, "name", None),
                "acknowledged_at": acked.get(e.id).isoformat() if acked.get(e.id) else None,
            })
        return policy, rows

    def outstanding_for(self, employee: Employee):
        acked_ids = set(
            PolicyAcknowledgement.objects.filter(
                tenant=self.tenant, employee=employee
            ).values_list("policy_id", flat=True)
        )
        return self.get_base_queryset().filter(
            is_active=True, requires_acknowledgement=True
        ).exclude(id__in=acked_ids)

    def acknowledged_for(self, employee: Employee):
        return PolicyAcknowledgement.objects.filter(
            tenant=self.tenant, employee=employee
        ).select_related("policy").order_by("-acknowledged_at")

    # ── writes ───────────────────────────────────────────────────────────
    @logged_operation(action="create", resource_type="policy_document", log_result=True)
    def create_policy(self, *, actor=None, file=None, **fields) -> PolicyDocument:
        data = {k: v for k, v in fields.items() if k in _EDITABLE}
        if not str(data.get("title", "")).strip():
            raise ValidationException("A policy title is required.")
        policy = self.create(
            created_by_id=getattr(actor, "id", None),
            file=file,
            **data,
        )
        record_hr_audit(
            self.tenant, actor=actor, action="policy.create",
            target_type="policy_document", target_id=policy.id, new_value=policy.title,
        )
        return policy

    @logged_operation(action="update", resource_type="policy_document")
    def update_policy(self, policy_id: Any, actor=None, file=None, **fields) -> PolicyDocument:
        policy = self.get_by_id(policy_id)
        data = {k: v for k, v in fields.items() if k in _EDITABLE}
        for key, value in data.items():
            setattr(policy, key, value)
        if file is not None:
            policy.file = file
        policy.save()
        record_hr_audit(
            self.tenant, actor=actor, action="policy.update",
            target_type="policy_document", target_id=policy_id,
        )
        return policy

    @logged_operation(action="delete", resource_type="policy_document")
    def delete_policy(self, policy_id: Any, actor=None) -> None:
        policy = self.get_by_id(policy_id)
        policy.delete()
        record_hr_audit(
            self.tenant, actor=actor, action="policy.delete",
            target_type="policy_document", target_id=policy_id,
        )

    @logged_operation(action="acknowledge", resource_type="policy_document")
    @transaction.atomic
    def acknowledge(self, policy_id: Any, employee: Employee, note: str = "") -> PolicyAcknowledgement:
        try:
            policy = PolicyDocument.objects.get(
                id=policy_id, tenant=self.tenant, is_active=True
            )
        except PolicyDocument.DoesNotExist:
            raise NotFoundException("Policy not found or no longer active.")
        try:
            ack, _ = PolicyAcknowledgement.objects.get_or_create(
                tenant=self.tenant, policy=policy, employee=employee,
                defaults={"note": note or ""},
            )
        except IntegrityError:
            ack = PolicyAcknowledgement.objects.get(
                tenant=self.tenant, policy=policy, employee=employee
            )
        record_hr_audit(
            self.tenant, actor=employee.user if hasattr(employee, "user") else None,
            action="policy.acknowledge", target_type="policy_document",
            target_id=policy.id, detail={"employee_id": str(employee.id)},
        )
        return ack
