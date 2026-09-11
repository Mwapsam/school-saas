"""Phase 4 — academic-year carry-forward / reconciliation.

At year rollover, each student's closing outstanding balance in the *from* year
is carried into the *to* year as an opening charge, and a FeeReconciliation
record links the two years. Idempotent via FeeReconciliation's unique constraint
(tenant, from_academic_year, to_academic_year, student).
"""
from decimal import Decimal
from typing import Dict, Any, List

from django.db import transaction
from django.db.models import Sum

from core.models import (
    AcademicYear, FeeCategory, FinanceFee, FeeTransaction, FeeReconciliation, Student,
)
from .logging_service import ServiceLogger

CARRY_FORWARD_CATEGORY_NAME = "Carry Forward (Previous Year)"


class FeeReconciliationService:
    def __init__(self, tenant):
        self.tenant = tenant
        self.logger = ServiceLogger('fee_reconciliation', tenant)

    def _carry_forward_category(self, to_year: AcademicYear) -> FeeCategory:
        category, _ = FeeCategory.objects.get_or_create(
            tenant=self.tenant,
            name=CARRY_FORWARD_CATEGORY_NAME,
            academic_year=to_year,
            defaults={"description": "Outstanding balance carried from the previous academic year"},
        )
        return category

    def student_outstanding(self, student, academic_year: AcademicYear) -> Decimal:
        return FinanceFee.objects.filter(
            tenant=self.tenant, student=student, academic_year=academic_year, balance__gt=0,
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

    @transaction.atomic
    def carry_forward_student(self, student, from_year: AcademicYear,
                              to_year: AcademicYear) -> FeeReconciliation:
        """Carry one student's closing outstanding from ``from_year`` into ``to_year``.

        Idempotent: if a reconciliation for this (from, to, student) already
        exists, it is returned unchanged and no duplicate opening charge is made.
        """
        existing = FeeReconciliation.objects.filter(
            tenant=self.tenant, from_academic_year=from_year,
            to_academic_year=to_year, student=student,
        ).first()
        if existing is not None:
            return existing

        outstanding = self.student_outstanding(student, from_year)

        recon = FeeReconciliation.objects.create(
            tenant=self.tenant, from_academic_year=from_year, to_academic_year=to_year,
            student=student, outstanding_amount=outstanding, is_processed=True,
        )

        if outstanding > 0:
            category = self._carry_forward_category(to_year)
            FinanceFee.objects.create(
                tenant=self.tenant, student=student, fee_category=category,
                academic_year=to_year, balance=outstanding, is_paid=False,
                particular_total=outstanding,
            )
            FeeTransaction.objects.create(
                tenant=self.tenant, student=student, fee_category=category,
                academic_year=to_year, transaction_type='adjustment',
                amount=outstanding,
                description=f"Opening balance carried from {from_year.name}",
            )

        self.logger.log_create(
            resource_type='fee_reconciliation', resource_id=str(recon.id),
            details={
                'student': getattr(student, 'admission_no', str(student.id)),
                'from_year': from_year.name, 'to_year': to_year.name,
                'outstanding': str(outstanding),
            },
        )
        return recon

    @transaction.atomic
    def carry_forward_year(self, from_year: AcademicYear, to_year: AcademicYear,
                           students: List[Student] = None) -> Dict[str, Any]:
        """Carry forward every student with an outstanding balance in ``from_year``.

        Returns a summary dict.
        """
        if students is None:
            student_ids = FinanceFee.objects.filter(
                tenant=self.tenant, academic_year=from_year, balance__gt=0,
            ).values_list('student_id', flat=True).distinct()
            students = Student.objects.filter(id__in=list(student_ids), tenant=self.tenant)

        processed = 0
        carried_total = Decimal('0.00')
        for student in students:
            recon = self.carry_forward_student(student, from_year, to_year)
            processed += 1
            carried_total += recon.outstanding_amount or Decimal('0.00')

        return {
            'from_year': from_year.name, 'to_year': to_year.name,
            'students_processed': processed, 'total_carried': carried_total,
        }
