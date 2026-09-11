"""Phase 1 regression tests: finance ledger is correctly tied to academic year.

Covers the cross-year payment mis-application bug and academic-year stamping on
charges, payments, and transactions in FinanceService.

Builds its own course/batch/student against the shared ``school`` fixture from
conftest (which operates in the public schema where the SHARED_APPS ``core``
tables live). We deliberately do NOT use conftest's course/student fixtures,
which are stale relative to the current models.
"""
import uuid
import pytest
from decimal import Decimal
from datetime import date

from core.models import (
    Course, Batch, Student, BatchStudent, AcademicYear,
    FeeCategory, FeeTransaction,
)
from core.services.finance_service import FinanceService


@pytest.fixture
def prior_year(db, school):
    return AcademicYear.objects.create(
        name=f"2023-2024-{uuid.uuid4().hex[:4]}",
        start_date=date(2023, 9, 1),
        end_date=date(2024, 7, 31),
        is_active=True,
        tenant=school,
    )


@pytest.fixture
def current_year(db, school, prior_year):
    # Saving this active auto-deactivates prior_year (model.save() behaviour).
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
        first_name="Pat", last_name="Learner",
        admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
        admission_date=date(2024, 9, 1),
        date_of_birth=date(2018, 1, 1),
        gender="male",
        tenant=school,
    )
    BatchStudent.objects.create(batch=batch, student=s, tenant=school)
    return s


@pytest.fixture
def fee_category(db, school):
    # Shared category reused across years (the conditions that triggered the bug).
    return FeeCategory.objects.create(name=f"Tuition-{uuid.uuid4().hex[:4]}", tenant=school)


@pytest.mark.django_db
@pytest.mark.unit
class TestFinanceAcademicYear:
    def test_payment_does_not_touch_prior_year_balance(
        self, school, student, fee_category, prior_year, current_year
    ):
        svc = FinanceService(school)
        fee_prior = svc.record_student_fee(
            str(student.id), str(fee_category.id), Decimal("100.00"),
            academic_year=prior_year,
        )
        fee_current = svc.record_student_fee(
            str(student.id), str(fee_category.id), Decimal("100.00"),
            academic_year=current_year,
        )

        txn, paid_fee = svc.process_fee_payment(
            str(student.id), str(fee_category.id), Decimal("40.00"),
            academic_year=current_year,
        )

        fee_prior.refresh_from_db()
        fee_current.refresh_from_db()

        # The current year's charge is reduced; the prior year's is untouched.
        assert fee_current.balance == Decimal("60.00")
        assert fee_prior.balance == Decimal("100.00")
        assert paid_fee.id == fee_current.id

        # The payment ledger row + transaction are stamped with the right year.
        ft = FeeTransaction.objects.get(
            student=student, transaction_type="payment", amount=Decimal("40.00")
        )
        assert ft.academic_year_id == current_year.id
        assert txn.academic_year_id == current_year.id

    def test_record_student_fee_stamps_year(
        self, school, student, fee_category, current_year
    ):
        svc = FinanceService(school)
        fee = svc.record_student_fee(
            str(student.id), str(fee_category.id), Decimal("50.00"),
            academic_year=current_year,
        )
        assert fee.academic_year_id == current_year.id

    def test_payment_defaults_to_active_year(
        self, school, student, fee_category, prior_year, current_year
    ):
        svc = FinanceService(school)
        # Charge only exists for the active (current) year.
        fee_current = svc.record_student_fee(
            str(student.id), str(fee_category.id), Decimal("80.00"),
            academic_year=current_year,
        )

        # No academic_year passed -> resolves to the tenant's active year.
        _, paid_fee = svc.process_fee_payment(
            str(student.id), str(fee_category.id), Decimal("30.00"),
        )

        fee_current.refresh_from_db()
        assert fee_current.balance == Decimal("50.00")
        assert paid_fee.id == fee_current.id
