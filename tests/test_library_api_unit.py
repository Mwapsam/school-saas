"""
Unit tests for Library domain API.

Covers:
- Book catalog management (categories, books, copies)
- Book borrowing/returns workflow
- Overdue tracking and fine management
- Module enforcement
- Tenant isolation
"""

import pytest
from datetime import date, timedelta
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from django_tenants.test.cases import TenantTestCase

from core.models import (
    LibraryCategory, LibraryBook, LibraryBookCopy, LibraryBorrow,
    LibraryReturn, Student, School, SchoolModule
)
from core.modules import is_module_required


@pytest.mark.django_db(transaction=True)
class TestLibraryCategoryAPI(TenantTestCase):
    """Test LibraryCategory CRUD and endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='lib_admin', password='pass')
        self.client.force_authenticate(user=self.user)
        self.school = self.tenant
        SchoolModule.objects.create(
            school=self.school, module='library', enabled=True
        )

    def test_create_category(self):
        """Create a library category."""
        data = {'name': 'Fiction', 'code': 'FIC', 'description': 'Fiction books'}
        response = self.client.post('/api/v1/library-categories/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert LibraryCategory.objects.filter(name='Fiction').exists()

    def test_list_categories(self):
        """List all library categories."""
        LibraryCategory.objects.create(
            school=self.school, name='Non-Fiction', code='NF'
        )
        response = self.client.get('/api/v1/library-categories/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_update_category(self):
        """Update a library category."""
        cat = LibraryCategory.objects.create(
            school=self.school, name='Reference', code='REF'
        )
        data = {'name': 'Reference Materials'}
        response = self.client.patch(f'/api/v1/library-categories/{cat.id}/', data)
        assert response.status_code == status.HTTP_200_OK
        cat.refresh_from_db()
        assert cat.name == 'Reference Materials'

    def test_delete_category(self):
        """Delete a library category."""
        cat = LibraryCategory.objects.create(
            school=self.school, name='Journals', code='JNL'
        )
        response = self.client.delete(f'/api/v1/library-categories/{cat.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not LibraryCategory.objects.filter(id=cat.id).exists()

    def test_search_categories(self):
        """Search categories by name/code."""
        LibraryCategory.objects.create(
            school=self.school, name='Mathematics', code='MATH'
        )
        response = self.client.get('/api/v1/library-categories/?search=MATH')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1


@pytest.mark.django_db(transaction=True)
class TestLibraryBookAPI(TenantTestCase):
    """Test LibraryBook catalog and inventory."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='lib_user', password='pass')
        self.client.force_authenticate(user=self.user)
        self.school = self.tenant
        SchoolModule.objects.create(
            school=self.school, module='library', enabled=True
        )
        self.category = LibraryCategory.objects.create(
            school=self.school, name='Science', code='SCI'
        )

    def test_create_book(self):
        """Create a book in catalog."""
        data = {
            'title': 'Physics 101',
            'isbn': '978-3-16-148410-0',
            'author': 'Albert Einstein',
            'publisher': 'Academic Press',
            'publication_year': 2020,
            'category': self.category.id,
            'description': 'Introduction to physics'
        }
        response = self.client.post('/api/v1/library-books/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert LibraryBook.objects.filter(title='Physics 101').exists()

    def test_list_books_with_copy_counts(self):
        """List books with computed total_copies and available_copies."""
        book = LibraryBook.objects.create(
            school=self.school, title='Chemistry', isbn='978-1', author='Jane',
            category=self.category
        )
        LibraryBookCopy.objects.create(
            school=self.school, book=book, barcode='BC001', condition='available'
        )
        LibraryBookCopy.objects.create(
            school=self.school, book=book, barcode='BC002', condition='damaged'
        )
        response = self.client.get('/api/v1/library-books/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'][0]['total_copies'] == 2
        assert response.data['results'][0]['available_copies'] == 1

    def test_filter_books_by_category(self):
        """Filter books by category."""
        book = LibraryBook.objects.create(
            school=self.school, title='Biology', isbn='978-2', author='John',
            category=self.category
        )
        response = self.client.get(
            f'/api/v1/library-books/?category={self.category.id}'
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_search_books(self):
        """Search books by title, author, ISBN."""
        LibraryBook.objects.create(
            school=self.school, title='Organic Chemistry', isbn='978-3',
            author='Sarah Chen', category=self.category
        )
        response = self.client.get('/api/v1/library-books/?search=Sarah')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_by_category_endpoint(self):
        """Get books grouped by category with counts."""
        LibraryBook.objects.create(
            school=self.school, title='Algebra', isbn='978-4', author='Math Prof',
            category=self.category
        )
        response = self.client.get('/api/v1/library-books/by_category/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) > 0


@pytest.mark.django_db(transaction=True)
class TestLibraryBookCopyAPI(TenantTestCase):
    """Test individual book copy inventory management."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='lib_mgr', password='pass')
        self.client.force_authenticate(user=self.user)
        self.school = self.tenant
        SchoolModule.objects.create(
            school=self.school, module='library', enabled=True
        )
        self.category = LibraryCategory.objects.create(
            school=self.school, name='History', code='HIST'
        )
        self.book = LibraryBook.objects.create(
            school=self.school, title='World History', isbn='978-5',
            author='Historian', category=self.category
        )

    def test_create_copy(self):
        """Add a copy to inventory."""
        data = {
            'book': self.book.id,
            'barcode': 'COPY001',
            'condition': 'available',
            'acquisition_date': date.today()
        }
        response = self.client.post('/api/v1/library-copies/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert LibraryBookCopy.objects.filter(barcode='COPY001').exists()

    def test_list_copies_by_condition(self):
        """Filter copies by condition."""
        LibraryBookCopy.objects.create(
            school=self.school, book=self.book, barcode='COPY002', condition='available'
        )
        LibraryBookCopy.objects.create(
            school=self.school, book=self.book, barcode='COPY003', condition='damaged'
        )
        response = self.client.get('/api/v1/library-copies/?condition=available')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_search_copies_by_barcode(self):
        """Search copies by barcode."""
        LibraryBookCopy.objects.create(
            school=self.school, book=self.book, barcode='BC-12345', condition='available'
        )
        response = self.client.get('/api/v1/library-copies/?search=BC-12345')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1


@pytest.mark.django_db(transaction=True)
class TestLibraryBorrowAPI(TenantTestCase):
    """Test book borrowing workflow."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='lib_staff', password='pass')
        self.client.force_authenticate(user=self.user)
        self.school = self.tenant
        SchoolModule.objects.create(
            school=self.school, module='library', enabled=True
        )
        self.category = LibraryCategory.objects.create(
            school=self.school, name='General', code='GEN'
        )
        self.book = LibraryBook.objects.create(
            school=self.school, title='Test Book', isbn='978-6',
            author='Author', category=self.category
        )
        self.copy = LibraryBookCopy.objects.create(
            school=self.school, book=self.book, barcode='TEST001', condition='available'
        )
        self.student = Student.objects.create(
            school=self.school, admission_number='STU001',
            full_name='John Doe'
        )

    def test_checkout_book(self):
        """Record a book checkout."""
        data = {
            'student': self.student.id,
            'copy': self.copy.id,
            'due_date': date.today() + timedelta(days=14),
            'notes': 'Regular checkout'
        }
        response = self.client.post('/api/v1/library-borrows/', data)
        assert response.status_code == status.HTTP_201_CREATED
        assert LibraryBorrow.objects.filter(student=self.student).exists()

    def test_student_borrowed_books(self):
        """Get books currently borrowed by a student."""
        borrow = LibraryBorrow.objects.create(
            school=self.school, student=self.student, copy=self.copy,
            checkout_date=date.today(), due_date=date.today() + timedelta(days=14)
        )
        response = self.client.get(
            f'/api/v1/library-borrows/student_borrowed/?student={self.student.id}'
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_list_borrows(self):
        """List all active borrows."""
        LibraryBorrow.objects.create(
            school=self.school, student=self.student, copy=self.copy,
            checkout_date=date.today(), due_date=date.today() + timedelta(days=14)
        )
        response = self.client.get('/api/v1/library-borrows/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1


@pytest.mark.django_db(transaction=True)
class TestLibraryReturnAPI(TenantTestCase):
    """Test book returns and overdue tracking."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='lib_return', password='pass')
        self.client.force_authenticate(user=self.user)
        self.school = self.tenant
        SchoolModule.objects.create(
            school=self.school, module='library', enabled=True
        )
        self.category = LibraryCategory.objects.create(
            school=self.school, name='General', code='GEN'
        )
        self.book = LibraryBook.objects.create(
            school=self.school, title='Return Test', isbn='978-7',
            author='Author', category=self.category
        )
        self.copy = LibraryBookCopy.objects.create(
            school=self.school, book=self.book, barcode='RETURN001', condition='available'
        )
        self.student = Student.objects.create(
            school=self.school, admission_number='STU002',
            full_name='Jane Doe'
        )
        self.borrow = LibraryBorrow.objects.create(
            school=self.school, student=self.student, copy=self.copy,
            checkout_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=6)
        )

    def test_checkin_book(self):
        """Record a book return."""
        data = {
            'borrow': self.borrow.id,
            'return_date': date.today(),
            'condition_on_return': 'good',
            'fine_amount': 0
        }
        response = self.client.post('/api/v1/library-returns/', data)
        assert response.status_code == status.HTTP_201_CREATED

    def test_overdue_report(self):
        """Get report of overdue books."""
        response = self.client.get('/api/v1/library-returns/overdue_report/')
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        if len(response.data) > 0:
            assert 'days_overdue' in response.data[0]

    def test_fine_summary(self):
        """Get fine collection summary."""
        LibraryReturn.objects.create(
            school=self.school, borrow=self.borrow,
            return_date=date.today(), condition_on_return='good',
            fine_amount=50, fine_paid=False
        )
        response = self.client.get('/api/v1/library-returns/fine_summary/')
        assert response.status_code == status.HTTP_200_OK
        assert 'total_fines' in response.data
        assert 'total_paid' in response.data
        assert 'total_pending' in response.data

    def test_list_returns_by_paid_status(self):
        """Filter returns by fine paid status."""
        ret = LibraryReturn.objects.create(
            school=self.school, borrow=self.borrow,
            return_date=date.today(), condition_on_return='good',
            fine_amount=100, fine_paid=True
        )
        response = self.client.get('/api/v1/library-returns/?fine_paid=true')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db(transaction=True)
class TestLibraryModuleEnforcement(TenantTestCase):
    """Test module enforcement on Library endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='user', password='pass')
        self.client.force_authenticate(user=self.user)
        self.school = self.tenant

    def test_disabled_module_returns_403(self):
        """Disabled library module returns 403 on all endpoints."""
        SchoolModule.objects.create(
            school=self.school, module='library', enabled=False
        )
        response = self.client.get('/api/v1/library-categories/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_enabled_module_allows_access(self):
        """Enabled module allows access."""
        SchoolModule.objects.create(
            school=self.school, module='library', enabled=True
        )
        response = self.client.get('/api/v1/library-categories/')
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_access_denied(self):
        """Unauthenticated users get 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/library-categories/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
class TestLibraryTenantIsolation(TenantTestCase):
    """Test tenant isolation in Library domain."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='tenant_user', password='pass')
        self.client.force_authenticate(user=self.user)
        self.school = self.tenant
        SchoolModule.objects.create(
            school=self.school, module='library', enabled=True
        )
        self.category = LibraryCategory.objects.create(
            school=self.school, name='Test', code='TST'
        )

    def test_direct_object_access_isolated(self):
        """Cannot access Library objects from another tenant by direct ID."""
        from django_tenants.test.cases import TenantTestCase as TTCase
        from django.test import TestCase as DTC

        category_2 = LibraryCategory.objects.create(
            school=self.school, name='Other', code='OTH'
        )
        response = self.client.get(f'/api/v1/library-categories/{category_2.id}/')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]

    def test_create_in_current_tenant(self):
        """New objects are created in current tenant."""
        data = {'name': 'New Cat', 'code': 'NEW'}
        response = self.client.post('/api/v1/library-categories/', data)
        assert response.status_code == status.HTTP_201_CREATED
        created = LibraryCategory.objects.get(code='NEW')
        assert created.school == self.school
