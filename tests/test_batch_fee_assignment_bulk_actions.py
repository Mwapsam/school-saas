"""Tests for Batch Fee Assignment bulk student selection and bulk delete functionality."""
import pytest
from datetime import date, datetime

from core.models import (
    FeeCategory, Batch, Student, BatchStudent, BatchFeeCategory,
    BatchFeeCategoryStudent, Term, FinanceFee, ExamGroup, FeeCollection,
    FeeParticular
)
from core.services.finance_service import FinanceService
from core.services.fee_collection_service import FeeCollectionService
from core.services.exceptions import NotFoundException, ValidationException


@pytest.mark.django_db
class TestAssignFeeToMultipleBatches:
    """Test FinanceService.assign_fee_to_batches with optional student scoping"""

    @pytest.fixture(autouse=True)
    def setup(self, db, school, course, batch, academic_year):
        """Use pytest fixtures instead of TestCase.setUp"""
        self.school = school
        self.academic_year = academic_year
        self.course = course

        self.fee_category = FeeCategory.objects.create(
            tenant=self.school, name='Tuition', is_deleted=False
        )
        # Create a FeeParticular for the category (required for fee generation)
        FeeParticular.objects.create(
            tenant=self.school, fee_category=self.fee_category,
            name='Tuition Fee', amount=1000.00, is_active=True
        )
        self.batch1 = batch
        self.batch2 = Batch.objects.create(
            tenant=self.school, name='Class 1B', is_active=True, is_deleted=False,
            course=self.course, academic_year=self.academic_year,
            start_date=datetime(2024, 1, 1), end_date=datetime(2024, 12, 31)
        )
        self.student1 = Student.objects.create(
            tenant=self.school, first_name='Alice', last_name='Smith',
            admission_no='ADM001', is_active=True, admission_date=date(2024, 1, 1),
            date_of_birth=date(2010, 5, 15)
        )
        self.student2 = Student.objects.create(
            tenant=self.school, first_name='Bob', last_name='Jones',
            admission_no='ADM002', is_active=True, admission_date=date(2024, 1, 1),
            date_of_birth=date(2010, 6, 20)
        )
        self.student3 = Student.objects.create(
            tenant=self.school, first_name='Carol', last_name='White',
            admission_no='ADM003', is_active=True, admission_date=date(2024, 1, 1),
            date_of_birth=date(2010, 7, 25)
        )
        # Enroll students in batches
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch1, student=self.student1, is_active=True
        )
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch1, student=self.student2, is_active=True
        )
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch2, student=self.student2, is_active=True
        )
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch2, student=self.student3, is_active=True
        )
        self.svc = FinanceService(self.school)

    def test_assign_fee_to_multiple_batches_no_students(self):
        """Create assignments for multiple batches without student scoping."""
        result = self.svc.assign_fee_to_batches(
            str(self.fee_category.id),
            [str(self.batch1.id), str(self.batch2.id)]
        )
        assert result['created_count'] == 2
        assert result['skipped_batches'] == []
        assert len(result['assignment_ids']) == 2

        # Verify no BatchFeeCategoryStudent rows (unscoped = whole batch)
        for assignment_id in result['assignment_ids']:
            bfc = BatchFeeCategory.objects.get(id=assignment_id)
            assert bfc.scoped_students.count() == 0

    def test_assign_fee_to_multiple_batches_with_students(self):
        """Create assignments scoped to selected students per batch."""
        result = self.svc.assign_fee_to_batches(
            str(self.fee_category.id),
            [str(self.batch1.id), str(self.batch2.id)],
            student_ids=[str(self.student1.id), str(self.student2.id), str(self.student3.id)]
        )
        assert result['created_count'] == 2
        assert result['zero_student_batches'] == []

        # For batch1: should have student1 and student2
        bfc1 = BatchFeeCategory.objects.get(batch=self.batch1, fee_category=self.fee_category)
        scoped_ids_1 = set(
            str(id) for id in bfc1.scoped_students.values_list('student_id', flat=True)
        )
        assert str(self.student1.id) in scoped_ids_1
        assert str(self.student2.id) in scoped_ids_1
        assert str(self.student3.id) not in scoped_ids_1  # Not enrolled in batch1

        # For batch2: should have student2 and student3
        bfc2 = BatchFeeCategory.objects.get(batch=self.batch2, fee_category=self.fee_category)
        scoped_ids_2 = set(
            str(id) for id in bfc2.scoped_students.values_list('student_id', flat=True)
        )
        assert str(self.student1.id) not in scoped_ids_2  # Not enrolled in batch2
        assert str(self.student2.id) in scoped_ids_2
        assert str(self.student3.id) in scoped_ids_2

    def test_assign_fee_student_not_enrolled_excluded(self):
        """Student not enrolled in a batch is excluded from that batch's scoping."""
        # Try to assign to batch2 with student1 (not in batch2)
        result = self.svc.assign_fee_to_batches(
            str(self.fee_category.id),
            [str(self.batch2.id)],
            student_ids=[str(self.student1.id), str(self.student2.id)]
        )
        # Assignment created, but student1 excluded from scoping
        assert result['created_count'] == 1
        bfc = BatchFeeCategory.objects.get(batch=self.batch2, fee_category=self.fee_category)
        scoped_ids = set(
            str(id) for id in bfc.scoped_students.values_list('student_id', flat=True)
        )
        assert str(self.student1.id) not in scoped_ids  # Excluded
        assert str(self.student2.id) in scoped_ids

    def test_assign_fee_zero_students_in_batch_surfaced(self):
        """When no selected students are enrolled in a batch, it's flagged."""
        # Try to assign with only student1, who is not in batch2
        result = self.svc.assign_fee_to_batches(
            str(self.fee_category.id),
            [str(self.batch2.id)],
            student_ids=[str(self.student1.id)]  # Not in batch2
        )
        assert result['created_count'] == 1
        assert self.batch2.name in result['zero_student_batches']

    def test_assign_fee_duplicate_skipped(self):
        """Skip batches that already have the assignment."""
        # Create first assignment
        self.svc.assign_fee_to_batches(
            str(self.fee_category.id),
            [str(self.batch1.id)]
        )
        # Try to assign same fee to same batch again
        result = self.svc.assign_fee_to_batches(
            str(self.fee_category.id),
            [str(self.batch1.id), str(self.batch2.id)]
        )
        assert result['created_count'] == 1  # Only batch2
        assert self.batch1.name in result['skipped_batches']
        assert self.batch2.name not in result['skipped_batches']

    def test_assign_fee_not_found_raises_notfound(self):
        """Raise NotFoundException for invalid fee category."""
        with pytest.raises(NotFoundException, match='Fee category'):
            self.svc.assign_fee_to_batches(
                '00000000-0000-0000-0000-000000000000',
                [str(self.batch1.id)]
            )

    def test_assign_fee_no_valid_batches_raises_validation(self):
        """Raise ValidationException when no valid batches found."""
        with pytest.raises(ValidationException, match='No valid batches'):
            self.svc.assign_fee_to_batches(
                str(self.fee_category.id),
                ['00000000-0000-0000-0000-000000000000']
            )


@pytest.mark.django_db
class TestBulkDeleteBatchFeeAssignments:
    """Test FinanceService.bulk_delete_batch_fee_assignments"""

    @pytest.fixture(autouse=True)
    def setup(self, db, school, course, batch, academic_year):
        """Use pytest fixtures instead of TestCase.setUp"""
        self.school = school
        self.course = course
        self.academic_year = academic_year

        self.fee_category = FeeCategory.objects.create(
            tenant=self.school, name='Tuition', is_deleted=False
        )
        # Create a FeeParticular for the category (required for fee generation)
        FeeParticular.objects.create(
            tenant=self.school, fee_category=self.fee_category,
            name='Tuition Fee', amount=1000.00, is_active=True
        )
        self.batch1 = batch
        self.batch2 = Batch.objects.create(
            tenant=self.school, name='Class 1B', is_active=True, is_deleted=False,
            course=self.course, academic_year=self.academic_year,
            start_date=datetime(2024, 1, 1), end_date=datetime(2024, 12, 31)
        )
        self.student = Student.objects.create(
            tenant=self.school, first_name='John', last_name='Doe',
            admission_no='ADM001', is_active=True, admission_date=date(2024, 1, 1),
            date_of_birth=date(2010, 5, 15)
        )
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch1, student=self.student, is_active=True
        )
        self.bfc1 = BatchFeeCategory.objects.create(
            tenant=self.school, fee_category=self.fee_category, batch=self.batch1
        )
        self.bfc2 = BatchFeeCategory.objects.create(
            tenant=self.school, fee_category=self.fee_category, batch=self.batch2
        )
        # Add student scoping to bfc1
        BatchFeeCategoryStudent.objects.create(
            tenant=self.school, batch_fee_category=self.bfc1, student=self.student
        )
        self.svc = FinanceService(self.school)

    def test_bulk_delete_assignments_succeeds(self):
        """Delete multiple assignments successfully."""
        result = self.svc.bulk_delete_batch_fee_assignments(
            [str(self.bfc1.id), str(self.bfc2.id)]
        )
        assert result['deleted_count'] == 2
        assert BatchFeeCategory.objects.filter(id__in=[self.bfc1.id, self.bfc2.id]).count() == 0

    def test_bulk_delete_cascades_scoped_students(self):
        """Cascading delete cleans up BatchFeeCategoryStudent rows."""
        # Verify scoped_students exist
        assert self.bfc1.scoped_students.count() == 1
        # Delete the assignment
        self.svc.bulk_delete_batch_fee_assignments([str(self.bfc1.id)])
        # Verify scoped_students rows are gone too
        assert BatchFeeCategoryStudent.objects.filter(
            batch_fee_category=self.bfc1
        ).count() == 0

    def test_bulk_delete_partial_invalid_ids(self):
        """Handle non-existent ids gracefully."""
        fake_id = '00000000-0000-0000-0000-000000000000'
        result = self.svc.bulk_delete_batch_fee_assignments(
            [str(self.bfc1.id), fake_id, str(self.bfc2.id)]
        )
        # Only valid ids are deleted
        assert result['deleted_count'] == 2
        assert BatchFeeCategory.objects.filter(id__in=[self.bfc1.id, self.bfc2.id]).count() == 0


@pytest.mark.django_db
class TestSyncStudentEnrollmentRespectScoping:
    """Test that FeeCollectionService.sync_student_enrollment respects BatchFeeCategoryStudent scoping"""

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
        # Create a FeeParticular for the category (required for fee generation)
        FeeParticular.objects.create(
            tenant=self.school, fee_category=self.fee_category,
            name='Tuition Fee', amount=1000.00, is_active=True
        )
        self.student_a = Student.objects.create(
            tenant=self.school, first_name='Alice', last_name='Smith',
            admission_no='ADM001', is_active=True, admission_date=date(2024, 1, 1),
            date_of_birth=date(2010, 5, 15)
        )
        self.student_b = Student.objects.create(
            tenant=self.school, first_name='Bob', last_name='Jones',
            admission_no='ADM002', is_active=True, admission_date=date(2024, 1, 1),
            date_of_birth=date(2010, 6, 20)
        )
        # Create FeeCollection with an unscoped BatchFeeCategory
        self.collection = self._create_collection_with_bfc()
        self.svc = FeeCollectionService(self.school)

    def _create_collection_with_bfc(self):
        """Helper to create FeeCollection and its BatchFeeCategory."""
        collection = FeeCollection.objects.create(
            tenant=self.school,
            name='Term 1 Unscoped',
            fee_category=self.fee_category,
            batch=self.batch,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            due_date=date(2024, 2, 15),
            status='published'
        )
        # Create unscoped BatchFeeCategory
        bfc = BatchFeeCategory.objects.create(
            tenant=self.school,
            fee_category=self.fee_category,
            batch=self.batch
        )
        return collection

    def test_sync_unscoped_charges_all_students(self):
        """Unscoped (empty BatchFeeCategoryStudent) charges all students in batch."""
        # Enroll both students
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch, student=self.student_a, is_active=True
        )
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch, student=self.student_b, is_active=True
        )
        # Sync enrollment for student_a
        self.svc.sync_student_enrollment(self.batch, self.student_a)
        # Sync enrollment for student_b
        self.svc.sync_student_enrollment(self.batch, self.student_b)

        # Both should have FinanceFee for this collection
        assert FinanceFee.objects.filter(
            tenant=self.school, student=self.student_a, fee_collection=self.collection
        ).exists()
        assert FinanceFee.objects.filter(
            tenant=self.school, student=self.student_b, fee_collection=self.collection
        ).exists()

    def test_sync_scoped_charges_only_selected_students(self):
        """Scoped BatchFeeCategoryStudent limits charging to selected students."""
        # Enroll both students
        bs_a = BatchStudent.objects.create(
            tenant=self.school, batch=self.batch, student=self.student_a, is_active=True
        )
        bs_b = BatchStudent.objects.create(
            tenant=self.school, batch=self.batch, student=self.student_b, is_active=True
        )

        # Delete setUp's collection and bfc (cross-collection check prevents dual charging)
        FeeCollection.objects.filter(id=self.collection.id).delete()
        BatchFeeCategory.objects.filter(
            tenant=self.school, fee_category=self.fee_category, batch=self.batch
        ).delete()

        # Create a scoped assignment (only student_a)
        scoped_collection = FeeCollection.objects.create(
            tenant=self.school,
            name='Term 1 Scoped',
            fee_category=self.fee_category,
            batch=self.batch,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            due_date=date(2024, 2, 15),
            status='published'
        )
        bfc_scoped = BatchFeeCategory.objects.create(
            tenant=self.school,
            fee_category=self.fee_category,
            batch=self.batch
        )
        BatchFeeCategoryStudent.objects.create(
            tenant=self.school,
            batch_fee_category=bfc_scoped,
            student=self.student_a  # Only student_a
        )

        # Sync for both students
        self.svc.sync_student_enrollment(self.batch, self.student_a)
        self.svc.sync_student_enrollment(self.batch, self.student_b)

        # Only student_a should have fee for scoped collection
        assert FinanceFee.objects.filter(
            tenant=self.school, student=self.student_a, fee_collection=scoped_collection
        ).exists()
        assert not FinanceFee.objects.filter(
            tenant=self.school, student=self.student_b, fee_collection=scoped_collection
        ).exists()

    def test_sync_scoped_empty_intersection_no_fees(self):
        """When no selected students are enrolled in batch, no fees generated (empty intersection)."""
        # Enroll only student_b
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch, student=self.student_b, is_active=True
        )

        # Delete the unscoped bfc from setUp so we can create a scoped one for this test
        BatchFeeCategory.objects.filter(
            tenant=self.school, fee_category=self.fee_category, batch=self.batch
        ).delete()

        # Create scoped assignment with student_a (who is not enrolled)
        scoped_collection = FeeCollection.objects.create(
            tenant=self.school,
            name='Term 1 Scoped Empty',
            fee_category=self.fee_category,
            batch=self.batch,
            academic_year=self.academic_year,
            term=self.term,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            due_date=date(2024, 2, 15),
            status='published'
        )
        bfc_scoped = BatchFeeCategory.objects.create(
            tenant=self.school,
            fee_category=self.fee_category,
            batch=self.batch
        )
        BatchFeeCategoryStudent.objects.create(
            tenant=self.school,
            batch_fee_category=bfc_scoped,
            student=self.student_a
        )

        # Sync for student_b
        self.svc.sync_student_enrollment(self.batch, self.student_b)

        # student_b should not have fee because they're not in the scoped list
        assert not FinanceFee.objects.filter(
            tenant=self.school, student=self.student_b, fee_collection=scoped_collection
        ).exists()
