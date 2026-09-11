"""Tests for Fee Collection bulk edit and bulk delete functionality."""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal

from core.models import (
    FeeCollection, FeeCategory, Term, Student, BatchStudent,
    FinanceFee, FeeTransaction, ExamGroup
)
from core.services.fee_collection_service import FeeCollectionService
from core.services.exceptions import NotFoundException, ValidationException


@pytest.mark.django_db
class TestFeeCollectionBulkEdit:
    """Test FeeCollectionService.update_collection and bulk_update_collections"""

    @pytest.fixture(autouse=True)
    def setup(self, db, school, course, batch, academic_year):
        """Use pytest fixtures instead of TestCase.setUp"""
        self.school = school
        self.academic_year = academic_year
        self.course = course
        self.batch = batch

        self.exam_group = ExamGroup.objects.create(
            tenant=self.school, name='Term 1 Exams', batch=self.batch,
            exam_type='Mid-term', exam_date=date(2024, 2, 15)
        )
        self.exam_group2 = ExamGroup.objects.create(
            tenant=self.school, name='Term 2 Exams', batch=self.batch,
            exam_type='Mid-term', exam_date=date(2024, 5, 15)
        )
        # Phase 4: Terms are year-scoped via academic_year, not exam_group.
        self.term = Term.objects.create(
            tenant=self.school, academic_year=self.academic_year, name='Term 1',
            start_date=date(2024, 1, 1), end_date=date(2024, 3, 31), order=1
        )
        self.term2 = Term.objects.create(
            tenant=self.school, academic_year=self.academic_year, name='Term 2',
            start_date=date(2024, 4, 1), end_date=date(2024, 6, 30), order=2
        )
        self.fee_category = FeeCategory.objects.create(
            tenant=self.school, name='Tuition', is_deleted=False
        )
        self.collection = FeeCollection.objects.create(
            tenant=self.school,
            name='Term 1 Collection',
            fee_category=self.fee_category,
            batch=self.batch,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            due_date=date(2024, 2, 15),
            status='draft'
        )
        self.svc = FeeCollectionService(self.school)

    def test_update_collection_single_field(self):
        """Update single field on a collection."""
        result = self.svc.update_collection(
            str(self.collection.id),
            status='published'
        )
        assert result.status == 'published'
        self.collection.refresh_from_db()
        assert self.collection.status == 'published'

    def test_update_collection_multiple_fields(self):
        """Update multiple fields at once."""
        new_due = date(2024, 2, 28)
        result = self.svc.update_collection(
            str(self.collection.id),
            term_name=self.term2.name,
            due_date=new_due,
            status='closed'
        )
        assert result.term == self.term2
        assert result.due_date == new_due
        assert result.status == 'closed'

    def test_update_collection_not_found(self):
        """Raise NotFoundException for non-existent collection."""
        with pytest.raises(NotFoundException):
            self.svc.update_collection('00000000-0000-0000-0000-000000000000')

    def test_update_collection_due_date_before_start_raises_validation_error(self):
        """Raise ValidationException if due_date < start_date."""
        with pytest.raises(ValidationException, match='Due date cannot be before start date'):
            self.svc.update_collection(
                str(self.collection.id),
                start_date=date(2024, 3, 1),
                due_date=date(2024, 2, 1)
            )

    def test_update_collection_end_date_before_start_raises_validation_error(self):
        """Raise ValidationException if end_date < start_date."""
        with pytest.raises(ValidationException, match='End date cannot be before start date'):
            self.svc.update_collection(
                str(self.collection.id),
                start_date=date(2024, 3, 1),
                end_date=date(2024, 2, 1)
            )

    def test_update_collection_invalid_status_raises_validation_error(self):
        """Raise ValidationException for invalid status."""
        with pytest.raises(ValidationException, match='Invalid status'):
            self.svc.update_collection(
                str(self.collection.id),
                status='invalid_status'
            )

    def test_update_collection_ignores_none_values(self):
        """None values in fields dict are ignored."""
        old_status = self.collection.status
        result = self.svc.update_collection(
            str(self.collection.id),
            status=None,
            term_name=None
        )
        assert result.status == old_status
        assert result.term == self.collection.term

    def test_update_collection_ignores_disallowed_fields(self):
        """Fields not in allow-list are ignored."""
        result = self.svc.update_collection(
            str(self.collection.id),
            fee_category=self.fee_category,  # not allowed
            batch=self.batch  # not allowed
        )
        # Should still match original values
        assert result.fee_category == self.collection.fee_category
        assert result.batch == self.collection.batch

    def test_bulk_update_collections_all_valid(self):
        """Bulk update succeeds when all ids are valid."""
        collection2 = FeeCollection.objects.create(
            tenant=self.school,
            name='Term 2 Collection',
            fee_category=self.fee_category,
            batch=self.batch,
            academic_year=self.academic_year,
            term=self.term2,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 6, 30),
            due_date=date(2024, 5, 15),
            status='draft'
        )
        result = self.svc.bulk_update_collections(
            [str(self.collection.id), str(collection2.id)],
            status='published'
        )
        assert result['updated'] == 2
        assert result['skipped'] == []
        self.collection.refresh_from_db()
        collection2.refresh_from_db()
        assert self.collection.status == 'published'
        assert collection2.status == 'published'

    def test_bulk_update_collections_partial_failure(self):
        """Bulk update skips invalid ids, continues with rest."""
        collection2 = FeeCollection.objects.create(
            tenant=self.school,
            name='Term 2 Collection',
            fee_category=self.fee_category,
            batch=self.batch,
            academic_year=self.academic_year,
            term=self.term2,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 6, 30),
            due_date=date(2024, 5, 15),
            status='draft'
        )
        fake_id = '00000000-0000-0000-0000-000000000000'
        result = self.svc.bulk_update_collections(
            [str(self.collection.id), fake_id, str(collection2.id)],
            status='published'
        )
        assert result['updated'] == 2
        assert len(result['skipped']) == 1
        assert result['skipped'][0]['id'] == fake_id
        assert result['skipped'][0]['reason'] == 'not_found'

    def test_bulk_update_collections_validation_error_skipped(self):
        """Bulk update skips collections that fail validation."""
        collection2 = FeeCollection.objects.create(
            tenant=self.school,
            name='Term 2 Collection',
            fee_category=self.fee_category,
            batch=self.batch,
            academic_year=self.academic_year,
            term=self.term2,
            start_date=date(2024, 4, 1),
            end_date=date(2024, 6, 30),
            due_date=date(2024, 5, 15),
            status='draft'
        )
        # Update both with a due_date that's valid for collection1 but invalid for collection2
        # collection1: start=2024-01-01, so due=2024-02-01 is valid (2024-02-01 >= 2024-01-01)
        # collection2: start=2024-04-01, so due=2024-02-01 is invalid (2024-02-01 < 2024-04-01)
        result = self.svc.bulk_update_collections(
            [str(self.collection.id), str(collection2.id)],
            due_date=date(2024, 2, 1)
        )
        assert result['updated'] == 1
        assert len(result['skipped']) == 1


@pytest.mark.django_db
class TestFeeCollectionBulkDelete:
    """Test FeeCollectionService.delete_collection with bulk-delete view pattern"""

    @pytest.fixture(autouse=True)
    def setup(self, db, school, course, batch, academic_year):
        """Use pytest fixtures instead of TestCase.setUp"""
        self.school = school
        self.course = course
        self.batch = batch
        self.academic_year = academic_year

        self.exam_group = ExamGroup.objects.create(
            tenant=self.school, name='Term 1 Exams', batch=self.batch,
            exam_type='Mid-term', exam_date=date(2024, 2, 15)
        )
        # Phase 4: Terms are year-scoped via academic_year, not exam_group.
        self.term = Term.objects.create(
            tenant=self.school, academic_year=self.academic_year, name='Term 1',
            start_date=date(2024, 1, 1), end_date=date(2024, 3, 31), order=1
        )
        self.fee_category = FeeCategory.objects.create(
            tenant=self.school, name='Tuition', is_deleted=False
        )
        self.student = Student.objects.create(
            tenant=self.school, first_name='John', last_name='Doe',
            admission_no='ADM001', is_active=True, admission_date=date(2024, 1, 1),
            date_of_birth=date(2010, 5, 15)
        )
        self.collection = FeeCollection.objects.create(
            tenant=self.school,
            name='Term 1 Collection',
            fee_category=self.fee_category,
            batch=self.batch,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            due_date=date(2024, 2, 15),
            status='published'
        )
        self.svc = FeeCollectionService(self.school)

    def test_delete_collection_succeeds_when_no_payments(self):
        """Delete collection without any payments recorded."""
        collection_id = self.collection.id
        self.svc.delete_collection(str(collection_id))
        assert not FeeCollection.objects.filter(id=collection_id).exists()

    def test_delete_collection_blocked_when_payments_recorded(self):
        """Raise ValidationException if collection has payment-receiving fees."""
        # Create a fee for this student in this collection
        fee = FinanceFee.objects.create(
            tenant=self.school,
            student=self.student,
            batch=self.batch,
            fee_category=self.fee_category,
            fee_collection=self.collection,
            academic_year=self.academic_year,
            particular_total=Decimal('1000.00'),
            balance=Decimal('500.00')  # Payment recorded (balance < particular_total)
        )
        with pytest.raises(ValidationException, match='payments recorded'):
            self.svc.delete_collection(str(self.collection.id))
        # Collection should still exist
        assert FeeCollection.objects.filter(id=self.collection.id).exists()

    def test_delete_collection_allowed_when_no_balance(self):
        """Allow deletion even if fee exists but has zero balance (fully paid)."""
        # Create a fully paid fee (balance = 0)
        fee = FinanceFee.objects.create(
            tenant=self.school,
            student=self.student,
            batch=self.batch,
            fee_category=self.fee_category,
            fee_collection=self.collection,
            academic_year=self.academic_year,
            particular_total=Decimal('1000.00'),
            balance=Decimal('0.00')  # Fully paid
        )
        # Should still block because particular_total > balance (payment was recorded)
        with pytest.raises(ValidationException):
            self.svc.delete_collection(str(self.collection.id))
