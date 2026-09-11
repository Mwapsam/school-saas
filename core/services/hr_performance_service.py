"""Performance reviews / appraisals."""
from __future__ import annotations

from typing import Any, Iterable

from django.db import transaction
from django.utils import timezone

from core.models import Employee, PerformanceCriterion, PerformanceReview
from .base import TenantAwareService
from .exceptions import NotFoundException, ValidationException
from .hr_audit import record_hr_audit
from .logging_service import ServiceLogger, logged_operation

_EDITABLE = {
    "review_period", "review_date", "reviewer_id", "overall_rating", "objectives",
    "strengths", "improvement_areas", "development_actions", "reviewer_comments",
    "employee_comments", "next_review_date", "status",
}


class PerformanceService(TenantAwareService[PerformanceReview]):
    def __init__(self, tenant):
        super().__init__(PerformanceReview, tenant)
        self.logger = ServiceLogger("hr_performance", tenant)

    def list_reviews(self, *, employee_id: Any = None, status: str = None):
        qs = self.get_base_queryset().select_related("employee", "reviewer")
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if status:
            qs = qs.filter(status=status)
        return qs

    def overdue(self):
        """Reviews past their review date that are not yet completed — feeds the
        dashboard 'appraisals due' figure."""
        return self.get_base_queryset().filter(
            review_date__lte=timezone.localdate()
        ).exclude(status="completed")

    @logged_operation(action="create", resource_type="performance_review", log_result=True)
    @transaction.atomic
    def create_review(
        self,
        *,
        employee_id: Any,
        review_period: str,
        review_date,
        reviewer_id: Any = None,
        is_teacher_review: bool = None,
        actor=None,
    ) -> PerformanceReview:
        try:
            employee = Employee.objects.get(id=employee_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee {employee_id} not found")
        if not review_period.strip():
            raise ValidationException("A review period is required.")

        teacher = employee.is_teaching_staff if is_teacher_review is None else is_teacher_review
        review = self.create(
            employee=employee,
            reviewer_id=reviewer_id,
            review_period=review_period.strip(),
            review_date=review_date,
            is_teacher_review=teacher,
            created_by_id=getattr(actor, "id", None),
        )
        template = (
            PerformanceReview.TEACHER_CRITERIA if teacher
            else PerformanceReview.GENERIC_CRITERIA
        )
        PerformanceCriterion.objects.bulk_create([
            PerformanceCriterion(tenant=self.tenant, review=review, name=name, order=i)
            for i, name in enumerate(template)
        ])
        record_hr_audit(
            self.tenant, actor=actor, action="performance.create",
            target_type="employee", target_id=employee_id, new_value=review_period,
        )
        return review

    @logged_operation(action="update", resource_type="performance_review")
    def update_review(self, review_id: Any, actor=None, **fields) -> PerformanceReview:
        data = {k: v for k, v in fields.items() if k in _EDITABLE}
        return self.update(review_id, **data)

    @logged_operation(action="set_criteria", resource_type="performance_review")
    @transaction.atomic
    def set_criteria(self, review_id: Any, rows: Iterable[dict], actor=None) -> PerformanceReview:
        review = self.get_by_id(review_id)
        by_id = {str(c.id): c for c in review.criteria.all()}
        for row in rows:
            crit = by_id.get(str(row.get("id")))
            if not crit:
                continue
            crit.rating = row.get("rating")
            crit.comment = (row.get("comment") or "")[:500]
            crit.save(update_fields=["rating", "comment", "updated_at"])
        return review

    @logged_operation(action="complete", resource_type="performance_review", log_result=True)
    def complete_review(self, review_id: Any, actor=None) -> PerformanceReview:
        review = self.get_by_id(review_id)
        review.status = "completed"
        review.completed_at = timezone.now()
        review.save(update_fields=["status", "completed_at", "updated_at"])
        record_hr_audit(
            self.tenant, actor=actor, action="performance.complete",
            target_type="employee", target_id=review.employee_id,
            new_value=review.review_period,
        )
        return review
