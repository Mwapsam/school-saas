"""Staff onboarding checklists.

A checklist is created lazily by :meth:`OnboardingService.ensure_for_employee`
— called from ``EmployeeService.create_employee`` for every new hire, and again
on demand when the onboarding tab is first opened for an older employee.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from core.models import Employee, OnboardingChecklist, OnboardingItem
from .base import TenantAwareService
from .exceptions import NotFoundException, ValidationException
from .hr_audit import record_hr_audit
from .logging_service import ServiceLogger, logged_operation


class OnboardingService(TenantAwareService[OnboardingChecklist]):
    def __init__(self, tenant):
        super().__init__(OnboardingChecklist, tenant)
        self.logger = ServiceLogger("hr_onboarding", tenant)

    @transaction.atomic
    def ensure_for_employee(self, employee) -> OnboardingChecklist:
        """Idempotent — returns the existing checklist or creates one with the
        default item set."""
        checklist = OnboardingChecklist.objects.filter(
            tenant=self.tenant, employee=employee
        ).first()
        if checklist:
            return checklist
        checklist = OnboardingChecklist.objects.create(
            tenant=self.tenant, employee=employee
        )
        OnboardingItem.objects.bulk_create([
            OnboardingItem(
                tenant=self.tenant, checklist=checklist, label=label, order=idx
            )
            for idx, label in enumerate(OnboardingChecklist.DEFAULT_ITEMS)
        ])
        return checklist

    def get_for_employee(self, employee_id: Any) -> OnboardingChecklist:
        try:
            employee = Employee.objects.get(id=employee_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee {employee_id} not found")
        return self.ensure_for_employee(employee)

    def in_progress(self):
        """Checklists that are not yet complete — for the dashboard alert and
        the onboarding list page."""
        return (
            self.get_base_queryset()
            .filter(completed_at__isnull=True)
            .select_related("employee", "employee__employee_department")
            .prefetch_related("items")
        )

    @logged_operation(action="toggle_item", resource_type="onboarding_item")
    def toggle_item(self, item_id: Any, is_done: bool, actor=None, note: str = None) -> OnboardingItem:
        try:
            item = OnboardingItem.objects.select_related("checklist").get(
                id=item_id, tenant=self.tenant
            )
        except OnboardingItem.DoesNotExist:
            raise NotFoundException(f"Onboarding item {item_id} not found")
        item.is_done = is_done
        item.done_at = timezone.now() if is_done else None
        item.done_by_id = getattr(actor, "id", None) if is_done else None
        if note is not None:
            item.note = note
        item.save()
        self._recompute_completion(item.checklist)
        record_hr_audit(
            self.tenant, actor=actor, action="onboarding.item",
            target_type="employee", target_id=item.checklist.employee_id,
            field=item.label, new_value="done" if is_done else "pending",
        )
        return item

    @logged_operation(action="add_item", resource_type="onboarding_item")
    def add_item(self, employee_id: Any, label: str, actor=None) -> OnboardingItem:
        if not label.strip():
            raise ValidationException("An item label is required.")
        checklist = self.get_for_employee(employee_id)
        order = (checklist.items.count())
        item = OnboardingItem.objects.create(
            tenant=self.tenant, checklist=checklist, label=label.strip(), order=order
        )
        self._recompute_completion(checklist)
        return item

    def _recompute_completion(self, checklist: OnboardingChecklist) -> None:
        progress = checklist.progress()
        done = progress["total"] and progress["done"] == progress["total"]
        if done and checklist.completed_at is None:
            checklist.completed_at = timezone.now()
            checklist.save(update_fields=["completed_at", "updated_at"])
        elif not done and checklist.completed_at is not None:
            checklist.completed_at = None
            checklist.save(update_fields=["completed_at", "updated_at"])
