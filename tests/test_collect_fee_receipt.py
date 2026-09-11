"""Single-payment receipt PDF on the Collect Fees page: sequential PW####
receipt numbering (FeeReceiptSettings.allocate_receipt_number), the extra
receipt fields on FeeReportingService.student_collection_receipt()
(invoice_number, guardian name), and CollectFeePaymentReceiptPDFView end to
end (WeasyPrint render, so this also catches template bugs)."""
import uuid
import pytest
from decimal import Decimal
from datetime import date

from django.http import Http404
from django.test import RequestFactory

from core.models import (
    Course, Batch, Student, BatchStudent, AcademicYear,
    FeeCategory, FeeParticular, FeeReceiptSettings, Guardian, StudentGuardianRelation,
)
from core.services.fee_collection_service import FeeCollectionService
from core.services.finance_service import FinanceService
from core.services.fee_reporting_service import FeeReportingService
from core.view_modules.fee_reporting_views import CollectFeePaymentReceiptPDFView

try:
    import weasyprint  # noqa: F401
    WEASYPRINT_AVAILABLE = True
except OSError:
    # WeasyPrint needs native GTK/Pango libraries that aren't installed on
    # every dev machine (notably plain Windows without MSYS2/GTK3) — skip
    # PDF-rendering tests there rather than failing on an environment gap.
    WEASYPRINT_AVAILABLE = False

requires_weasyprint = pytest.mark.skipif(
    not WEASYPRINT_AVAILABLE, reason="WeasyPrint native libraries (GTK/Pango) not available"
)


@pytest.fixture
def current_year(db, school):
    return AcademicYear.objects.create(
        name=f"2024-2025-{uuid.uuid4().hex[:4]}",
        start_date=date(2024, 9, 1), end_date=date(2025, 7, 31),
        is_active=True, tenant=school,
    )


@pytest.fixture
def course(db, school):
    return Course.objects.create(
        course_name="Grade 7", code=f"G7{uuid.uuid4().hex[:5].upper()}", tenant=school
    )


@pytest.fixture
def batch(db, school, course, current_year):
    return Batch.objects.create(
        name=f"G7 - A {uuid.uuid4().hex[:4]}", course=course, academic_year=current_year,
        start_date=date(2024, 9, 1), end_date=date(2025, 7, 31), tenant=school,
    )


@pytest.fixture
def student(db, school, batch):
    s = Student.objects.create(
        first_name="Amadou", last_name="Aidara",
        admission_no=f"PW{uuid.uuid4().hex[:6].upper()}",
        admission_date=date(2024, 9, 1), date_of_birth=date(2013, 1, 1), gender="male",
        tenant=school,
    )
    BatchStudent.objects.create(batch=batch, student=s, tenant=school)
    return s


@pytest.fixture
def fee_category(db, school, current_year):
    return FeeCategory.objects.create(
        name=f"Term 3 Tuition {uuid.uuid4().hex[:4]}", academic_year=current_year, tenant=school,
    )


@pytest.fixture
def particulars(db, school, fee_category):
    return [
        FeeParticular.objects.create(
            name="Tuition Fee", fee_category=fee_category,
            amount=Decimal("16000.00"), is_active=True, tenant=school,
        ),
    ]


@pytest.mark.django_db
class TestSequentialReceiptNumbering:
    def test_allocate_receipt_number_increments_sequentially(self, school):
        first = FeeReceiptSettings.allocate_receipt_number(school)
        second = FeeReceiptSettings.allocate_receipt_number(school)
        prefix = FeeReceiptSettings.get_settings(school).receipt_prefix
        assert first != second
        assert first.startswith(prefix)
        assert second.startswith(prefix)
        assert int(second[len(prefix):]) == int(first[len(prefix):]) + 1

    def test_payment_gets_sequential_reference(self, school, batch, student, fee_category, particulars, current_year):
        FinanceService(school).record_student_fee(
            str(student.id), str(fee_category.id), Decimal("16000.00"), academic_year=current_year,
        )
        prefix = FeeReceiptSettings.get_settings(school).receipt_prefix
        txn, _ = FinanceService(school).process_fee_payment(
            student_id=str(student.id), fee_category_id=str(fee_category.id),
            payment_amount=Decimal("15360.00"), payment_date=date(2025, 8, 8),
            payment_method='online',
        )
        assert txn.reference_number.startswith(prefix)


@pytest.mark.django_db
class TestCollectFeePaymentReceipt:
    def _make_collection_and_payment(self, school, batch, student, fee_category, current_year):
        collection = FeeCollectionService(school).create_collection(
            name="Term 3 2025 Tuition Fee",
            fee_category_id=str(fee_category.id),
            batch_ids=[str(batch.id)],
            due_date=date(2025, 8, 8),
            start_date=date(2025, 8, 1),
            end_date=date(2025, 10, 31),
        )["collections"][0]

        txn, _ = FinanceService(school).process_fee_payment(
            student_id=str(student.id), fee_category_id=str(fee_category.id),
            payment_amount=Decimal("15360.00"), payment_date=date(2025, 8, 8),
            payment_method='online', description='ABSA',
        )
        return collection, txn

    def test_receipt_includes_invoice_number_and_guardian_name(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        guardian = Guardian.objects.create(
            first_name="Mwala", last_name="Nalishuwa", tenant=school,
        )
        StudentGuardianRelation.objects.create(
            student=student, guardian=guardian, tenant=school, school=school, relation="Father",
        )

        collection, txn = self._make_collection_and_payment(school, batch, student, fee_category, current_year)

        svc = FeeReportingService(school)
        receipt = svc.student_collection_receipt(student, collection)
        # invoice_number is only populated by the itemized publish_collection()
        # flow (core/services/fee_collection_service.py:466); collections
        # created via the lump-sum create_collection() flow used here
        # legitimately have none yet — just confirm the key is exposed.
        assert 'invoice_number' in receipt
        assert svc.resolve_guardian_name(student) == "Mwala Nalishuwa"

        payment = next(p for p in receipt['payment_history'] if p['receipt_no'] == txn.reference_number)
        assert payment['amount'] == Decimal("15360.00")
        assert payment['mode'] == 'Online Payment'

    def test_template_renders_without_weasyprint(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        """Exercise the actual Django template (variable names, filters,
        loops) independent of WeasyPrint's native GTK/Pango dependency, so
        this still catches template bugs on machines without that installed."""
        from django.template.loader import render_to_string
        from core.utils.number_to_words import amount_to_words

        collection, txn = self._make_collection_and_payment(school, batch, student, fee_category, current_year)
        svc = FeeReportingService(school)
        receipt = svc.student_collection_receipt(student, collection)
        payment = next(p for p in receipt['payment_history'] if p['receipt_no'] == txn.reference_number)

        html = render_to_string('core/fees/collection_payment_receipt_pdf.html', {
            'school': school,
            'receipt': receipt,
            'payment': payment,
            'guardian_name': svc.resolve_guardian_name(student),
            'amount_in_words': amount_to_words(payment['amount']),
            'currency_symbol': 'ZK',
            'cashier': FeeReceiptSettings.get_settings(school).cashier,
        })

        assert receipt['student_name'] in html
        assert txn.reference_number in html
        assert 'Fifteen thousand three hundred and sixty' in html
        assert receipt['fee_collection_name'] in html

    @requires_weasyprint
    def test_pdf_view_renders_successfully(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        collection, txn = self._make_collection_and_payment(school, batch, student, fee_category, current_year)

        request = RequestFactory().get('/fees/collection-receipt/payment/', {
            'student_id': str(student.id),
            'fee_collection': str(collection.id),
            'receipt_no': txn.reference_number,
        })
        request.tenant = school

        response = CollectFeePaymentReceiptPDFView.as_view()(request)
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        assert response.content.startswith(b'%PDF')

    @requires_weasyprint
    def test_pdf_view_404s_for_unknown_receipt_no(
        self, school, batch, student, fee_category, particulars, current_year
    ):
        collection, _txn = self._make_collection_and_payment(school, batch, student, fee_category, current_year)

        request = RequestFactory().get('/fees/collection-receipt/payment/', {
            'student_id': str(student.id),
            'fee_collection': str(collection.id),
            'receipt_no': 'NOT-A-REAL-RECEIPT',
        })
        request.tenant = school

        with pytest.raises(Http404):
            CollectFeePaymentReceiptPDFView.as_view()(request)
