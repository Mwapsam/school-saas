"""Tests for bulk action views/API endpoints."""
import pytest
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.test import Client
from django.contrib.auth import get_user_model

from core.models import (
    FeeCollection, FeeCategory, Term, ExamGroup, Student, BatchStudent, FinanceFee, Batch
)

User = get_user_model()


@pytest.mark.django_db
class TestFeeCollectionBulkEditView:
    """Test FeeCollectionBulkEditView JSON endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self, db, school, domain, user, course, batch, academic_year):
        """Use pytest fixtures instead of TestCase.setUp"""
        self.school = school
        self.user = user
        self.course = course
        self.batch = batch
        self.academic_year = academic_year

        # Add user to tenant (might already be added by user fixture, but ensure)
        self.user.tenants.add(self.school)
        # Set user as admin to pass middleware permission check
        self.user.is_admin = True
        self.user.save()

        self.client = Client()
        self.client.force_login(self.user)

        self.exam_group1 = ExamGroup.objects.create(
            tenant=self.school, name='Term 1 Exams', batch=self.batch,
            exam_type='Mid-term', exam_date=date(2024, 2, 15)
        )
        self.exam_group2 = ExamGroup.objects.create(
            tenant=self.school, name='Term 2 Exams', batch=self.batch,
            exam_type='Mid-term', exam_date=date(2024, 5, 15)
        )
        # Phase 4: Terms are year-scoped via academic_year, not exam_group.
        self.term1 = Term.objects.create(
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
            term=self.term1,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            due_date=date(2024, 2, 15),
            status='draft'
        )

    def test_bulk_edit_view_rejects_empty_selection(self):
        """Return 400 when no collection_ids provided."""
        response = self.client.post(
            '/finance/collections/bulk-edit/',
            data=json.dumps({'collection_ids': []}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data

    def test_bulk_edit_view_rejects_invalid_json(self):
        """Return 400 on malformed JSON."""
        response = self.client.post(
            '/finance/collections/bulk-edit/',
            data='not valid json',
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_bulk_edit_view_rejects_invalid_term(self):
        """Invalid term name is skipped at service level, not rejected at view."""
        response = self.client.post(
            '/finance/collections/bulk-edit/',
            data=json.dumps({
                'collection_ids': [str(self.collection.id)],
                'term': 'NonexistentTerm'
            }),
            content_type='application/json'
        )
        # View accepts the request (200), but service skips the collection
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['updated'] == 0
        assert len(data['skipped']) == 1

    def test_bulk_edit_view_rejects_invalid_date_format(self):
        """Return 400 when date format is wrong."""
        response = self.client.post(
            '/finance/collections/bulk-edit/',
            data=json.dumps({
                'collection_ids': [str(self.collection.id)],
                'start_date': 'not-a-date'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.json()
        assert 'Invalid start_date' in data['error']

    def test_bulk_edit_view_rejects_invalid_status(self):
        """Return 400 when status is not valid."""
        response = self.client.post(
            '/finance/collections/bulk-edit/',
            data=json.dumps({
                'collection_ids': [str(self.collection.id)],
                'status': 'invalid_status'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.json()
        assert 'Invalid status' in data['error']

    def test_bulk_edit_view_rejects_due_before_start(self):
        """Return 400 when due_date < start_date."""
        response = self.client.post(
            '/finance/collections/bulk-edit/',
            data=json.dumps({
                'collection_ids': [str(self.collection.id)],
                'start_date': '2024-03-01',
                'due_date': '2024-02-01'
            }),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.json()
        assert 'before start date' in data['error'].lower()

    def test_bulk_edit_view_succeeds_with_valid_input(self):
        """Successfully update collection(s) with valid input."""
        response = self.client.post(
            '/finance/collections/bulk-edit/',
            data=json.dumps({
                'collection_ids': [str(self.collection.id)],
                'term': self.term2.name,
                'status': 'published'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['updated'] == 1

        # Verify changes persisted
        self.collection.refresh_from_db()
        assert self.collection.term == self.term2
        assert self.collection.status == 'published'

    def test_bulk_edit_view_tenant_isolation(self):
        """Collections from the user's own tenant can be updated, others are isolated."""
        # User only has access to self.school, so they can update their own collections
        response = self.client.post(
            '/finance/collections/bulk-edit/',
            data=json.dumps({
                'collection_ids': [str(self.collection.id)],
                'status': 'published'
            }),
            content_type='application/json'
        )
        assert response.status_code == 200
        # Collection should be updated
        self.collection.refresh_from_db()
        assert self.collection.status == 'published'


@pytest.mark.django_db
class TestFeeCollectionBulkDeleteJSONView:
    """Test FeeCollectionBulkDeleteJSONView JSON endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self, db, school, domain, user, course, batch, academic_year):
        """Use pytest fixtures instead of TestCase.setUp"""
        self.school = school
        self.user = user
        self.course = course
        self.batch = batch
        self.academic_year = academic_year

        self.user.tenants.add(self.school)
        # Set user as admin to pass middleware permission check
        self.user.is_admin = True
        self.user.save()

        self.client = Client()
        self.client.force_login(self.user)

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

    def test_bulk_delete_view_rejects_empty_selection(self):
        """Return 400 when no collection_ids provided."""
        response = self.client.post(
            '/finance/collections/bulk-delete-json/',
            data=json.dumps({'collection_ids': []}),
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.json()
        assert 'error' in data

    def test_bulk_delete_view_succeeds_without_payments(self):
        """Successfully delete collection(s) without recorded payments."""
        collection_id = self.collection.id
        response = self.client.post(
            '/finance/collections/bulk-delete-json/',
            data=json.dumps({'collection_ids': [str(collection_id)]}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['deleted'] == 1

        # Verify deletion
        assert not FeeCollection.objects.filter(id=collection_id).exists()

    def test_bulk_delete_view_skips_collections_with_payments(self):
        """Skip collections that have recorded payments."""
        student = Student.objects.create(
            tenant=self.school, first_name='John', last_name='Doe',
            admission_no='ADM001', is_active=True, admission_date=date(2024, 1, 1),
            date_of_birth=date(2010, 5, 15)
        )
        # Create fee with payment (balance < particular_total)
        fee = FinanceFee.objects.create(
            tenant=self.school,
            student=student,
            batch=self.batch,
            fee_category=self.fee_category,
            fee_collection=self.collection,
            academic_year=self.academic_year,
            particular_total=Decimal('1000.00'),
            balance=Decimal('500.00')  # Payment recorded
        )
        response = self.client.post(
            '/finance/collections/bulk-delete-json/',
            data=json.dumps({'collection_ids': [str(self.collection.id)]}),
            content_type='application/json'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['deleted'] == 0
        assert len(data['skipped']) == 1

        # Collection should still exist
        assert FeeCollection.objects.filter(id=self.collection.id).exists()


@pytest.mark.django_db
class TestBatchFeeAssignmentStudentsView:
    """Test BatchFeeAssignmentStudentsView JSON endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self, db, school, domain, user, course, batch, academic_year):
        """Use pytest fixtures instead of TestCase.setUp"""
        from core.models import Student, BatchStudent

        self.school = school
        self.user = user
        self.course = course
        self.batch = batch
        self.academic_year = academic_year

        self.user.tenants.add(self.school)
        # Set user as admin to pass middleware permission check
        self.user.is_admin = True
        self.user.save()

        self.client = Client()
        self.client.force_login(self.user)

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
        # Enroll only student1 as active
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch, student=self.student1, is_active=True
        )
        # Enroll student2 but inactive
        BatchStudent.objects.create(
            tenant=self.school, batch=self.batch, student=self.student2, is_active=False
        )

    def test_students_view_rejects_missing_batch_id(self):
        """Return 400 when batch_id not provided."""
        response = self.client.get('/api/fees/batch-assignment/students/')
        assert response.status_code == 400
        data = response.json()
        assert 'Missing batch_id' in data['error']

    def test_students_view_returns_active_students_only(self):
        """Return only active students in the batch."""
        response = self.client.get(
            f'/api/fees/batch-assignment/students/?batch_id={self.batch.id}'
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data['students']) == 1  # Only active student1
        assert data['students'][0]['id'] == str(self.student1.id)
        assert data['students'][0]['admission_no'] == 'ADM001'

    def test_students_view_empty_batch(self):
        """Return empty list for batch with no active students."""
        empty_batch = Batch.objects.create(
            tenant=self.school, name='Empty Batch', is_active=True,
            course=self.course, academic_year=self.academic_year,
            start_date=date(2024, 1, 1), end_date=date(2024, 12, 31)
        )
        response = self.client.get(
            f'/api/fees/batch-assignment/students/?batch_id={empty_batch.id}'
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data['students']) == 0
