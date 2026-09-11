"""Itemized fee payments must produce a receipt-capable FinanceTransaction.

Regression test for the gap found in Task 10's end-to-end verification:
`FinanceService.process_itemized_fee_payment` wrote only per-allocation
`FeeTransaction` ledger rows and never created a `FinanceTransaction`, so
itemized payments never appeared on the fee receipts page and had no id to
build a `core:finance_fee_receipt_pdf` URL from.

Reuses the fixture style from ``tests/test_finance_academic_year.py``.
"""
import uuid
import pytest
from decimal import Decimal
from datetime import date

from core.models import (
    Course, Batch, Student, BatchStudent, AcademicYear,
    FeeCategory, FeeParticular, FinanceTransaction,
)
from core.services.finance_service import FinanceService


@pytest.fixture
def current_year(db, school):
    return AcademicYear.objects.create(
        name=f"2024-2025-{uuid.uuid4().hex[:4]}",
        start_date=date(2024, 9, 1),
        end_date=date(2025, 7, 31),
        is_active=True,
        tenant=school,
    )


@pytest.fixture
def course(db, school):
    return Course.objects.create(
        course_name="Grade 1", code=f"G1{uuid.uuid4().hex[:5].upper()}", tenant=school
    )


@pytest.fixture
def batch(db, school, course, current_year):
    return Batch.objects.create(
        name=f"Grade 1A {uuid.uuid4().hex[:4]}",
        course=course,
        academic_year=current_year,
        start_date=date(2024, 9, 1),
        end_date=date(2025, 7, 31),
        tenant=school,
    )


@pytest.fixture
def student(db, school, batch):
    s = Student.objects.create(
        first_name="Tasha", last_name="Learner",
        admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
        admission_date=date(2024, 9, 1),
        date_of_birth=date(2018, 1, 1),
        gender="female",
        tenant=school,
    )
    BatchStudent.objects.create(batch=batch, student=s, tenant=school)
    return s


@pytest.fixture
def fee_category(db, school):
    return FeeCategory.objects.create(name=f"Tuition-{uuid.uuid4().hex[:4]}", tenant=school)


@pytest.fixture
def particulars(db, school, fee_category):
    tuition = FeeParticular.objects.create(
        tenant=school, fee_category=fee_category, name="Tuition", amount=Decimal("5000.00"),
    )
    activity = FeeParticular.objects.create(
        tenant=school, fee_category=fee_category, name="Activity", amount=Decimal("300.00"),
    )
    return tuition, activity


@pytest.mark.django_db
@pytest.mark.unit
class TestItemizedPaymentReceipt:
    def test_itemized_payment_creates_one_finance_transaction(
        self, school, student, fee_category, current_year, particulars
    ):
        tuition, activity = particulars
        svc = FinanceService(school)
        svc.record_student_fee(
            str(student.id), str(fee_category.id), Decimal("5300.00"),
            academic_year=current_year,
        )

        before_count = FinanceTransaction.objects.filter(tenant=school).count()

        result = svc.process_itemized_fee_payment(
            student_id=str(student.id),
            allocations=[
                {"fee_category_id": str(fee_category.id), "particular_id": str(tuition.id), "amount": "5000.00"},
                {"fee_category_id": str(fee_category.id), "particular_id": str(activity.id), "amount": "100.00"},
            ],
            payment_method="cash",
            academic_year=current_year,
        )

        after_count = FinanceTransaction.objects.filter(tenant=school).count()

        # Exactly one new FinanceTransaction for the whole submission.
        assert after_count == before_count + 1

        assert "transaction_id" in result
        txn = FinanceTransaction.objects.get(id=result["transaction_id"])
        assert txn.amount == Decimal("5100.00")
        assert txn.student_id == student.id
        assert txn.academic_year_id == current_year.id
        assert txn.tenant_id == school.id
