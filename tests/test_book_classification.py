"""
Tests for book classification by type and school level (Issue #26).
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from core.models import Book, BookCategory, School
from core.services.library_service import LibraryService


@pytest.mark.django_db
class TestBookClassification(TestCase):
    """Test book classification by type and school level."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.school = School.objects.create(name="Test School")

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = self.school
        self.service = LibraryService(self.tenant)

        # Create a test category
        self.category = BookCategory.objects.create(
            tenant=self.tenant,
            name="Academic Books"
        )

    def test_book_creation_with_classification(self):
        """Test that books can be created with book_type and school_level."""
        book = self.service.create_book(
            title="Python Basics",
            author="John Doe",
            book_number="PB001",
            category_id=str(self.category.id),
            book_type="TEXTBOOK",
            school_level="LOWER_SCHOOL",
            total_copies=5
        )

        assert book.book_type == "TEXTBOOK"
        assert book.school_level == "LOWER_SCHOOL"
        assert book.title == "Python Basics"

    def test_book_default_classification_values(self):
        """Test that default values are applied when not specified."""
        book = self.service.create_book(
            title="Adventure Stories",
            author="Jane Smith",
            book_number="AS001",
            category_id=str(self.category.id),
            total_copies=3
        )

        assert book.book_type == "OTHER"
        assert book.school_level == "ALL"

    def test_filter_books_by_type(self):
        """Test filtering books by book_type."""
        # Create textbooks
        for i in range(3):
            self.service.create_book(
                title=f"Textbook {i}",
                author="Author",
                book_number=f"TB{i:03d}",
                category_id=str(self.category.id),
                book_type="TEXTBOOK",
                school_level="ALL"
            )

        # Create storybooks
        for i in range(2):
            self.service.create_book(
                title=f"Storybook {i}",
                author="Author",
                book_number=f"SB{i:03d}",
                category_id=str(self.category.id),
                book_type="STORYBOOK",
                school_level="ALL"
            )

        # Test filter
        textbooks = Book.objects.filter(tenant=self.tenant, book_type="TEXTBOOK")
        storybooks = Book.objects.filter(tenant=self.tenant, book_type="STORYBOOK")

        assert textbooks.count() == 3
        assert storybooks.count() == 2

    def test_filter_books_by_school_level(self):
        """Test filtering books by school_level."""
        # Create Lower School books
        for i in range(2):
            self.service.create_book(
                title=f"Lower School Book {i}",
                author="Author",
                book_number=f"LS{i:03d}",
                category_id=str(self.category.id),
                book_type="TEXTBOOK",
                school_level="LOWER_SCHOOL"
            )

        # Create Upper School books
        for i in range(2):
            self.service.create_book(
                title=f"Upper School Book {i}",
                author="Author",
                book_number=f"US{i:03d}",
                category_id=str(self.category.id),
                book_type="TEXTBOOK",
                school_level="UPPER_SCHOOL"
            )

        # Create All Levels books
        self.service.create_book(
            title="Universal Book",
            author="Author",
            book_number="UB001",
            category_id=str(self.category.id),
            book_type="TEXTBOOK",
            school_level="ALL"
        )

        # Test filters
        lower = Book.objects.filter(tenant=self.tenant, school_level="LOWER_SCHOOL")
        upper = Book.objects.filter(tenant=self.tenant, school_level="UPPER_SCHOOL")
        all_levels = Book.objects.filter(tenant=self.tenant, school_level="ALL")

        assert lower.count() == 2
        assert upper.count() == 2
        assert all_levels.count() == 1

    def test_filter_books_by_type_and_level_combined(self):
        """Test filtering books by both type and school level."""
        # Create combinations
        self.service.create_book(
            title="Lower Textbook",
            author="Author",
            book_number="LT001",
            category_id=str(self.category.id),
            book_type="TEXTBOOK",
            school_level="LOWER_SCHOOL"
        )

        self.service.create_book(
            title="Lower Storybook",
            author="Author",
            book_number="LST001",
            category_id=str(self.category.id),
            book_type="STORYBOOK",
            school_level="LOWER_SCHOOL"
        )

        self.service.create_book(
            title="Upper Textbook",
            author="Author",
            book_number="UT001",
            category_id=str(self.category.id),
            book_type="TEXTBOOK",
            school_level="UPPER_SCHOOL"
        )

        # Test combined filter
        lower_textbooks = Book.objects.filter(
            tenant=self.tenant,
            book_type="TEXTBOOK",
            school_level="LOWER_SCHOOL"
        )

        assert lower_textbooks.count() == 1
        assert lower_textbooks.first().title == "Lower Textbook"

    def test_all_book_type_choices_available(self):
        """Test that all book type choices are available."""
        expected_types = ["TEXTBOOK", "STORYBOOK", "TEACHER_RESOURCE", "REFERENCE", "OTHER"]
        actual_types = [choice[0] for choice in Book.BOOK_TYPE_CHOICES]

        assert set(expected_types) == set(actual_types)

    def test_all_school_level_choices_available(self):
        """Test that all school level choices are available."""
        expected_levels = ["LOWER_SCHOOL", "UPPER_SCHOOL", "ALL"]
        actual_levels = [choice[0] for choice in Book.SCHOOL_LEVEL_CHOICES]

        assert set(expected_levels) == set(actual_levels)

    def test_teacher_resource_book_type(self):
        """Test creating Teacher's Resource Books."""
        book = self.service.create_book(
            title="Teacher's Guide",
            author="Educational Team",
            book_number="TG001",
            category_id=str(self.category.id),
            book_type="TEACHER_RESOURCE",
            school_level="UPPER_SCHOOL"
        )

        assert book.book_type == "TEACHER_RESOURCE"
        assert book.school_level == "UPPER_SCHOOL"

    def test_book_classification_persists_after_update(self):
        """Test that classification is preserved when updating other fields."""
        book = self.service.create_book(
            title="Original Title",
            author="Author",
            book_number="PT001",
            category_id=str(self.category.id),
            book_type="TEXTBOOK",
            school_level="LOWER_SCHOOL"
        )

        # Update copies
        updated_book = self.service.update_book_copies(str(book.id), 10)

        assert updated_book.book_type == "TEXTBOOK"
        assert updated_book.school_level == "LOWER_SCHOOL"
        assert updated_book.total_copies == 10
