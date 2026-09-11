"""
Library domain API — library management and book circulation.

Covers:
- Book inventory (catalog, copies, condition)
- Book categories/classifications
- Library members (who can borrow)
- Book borrowing (checkout, due dates)
- Book returns (checkin, overdue tracking)
- Fines and penalties for overdue books

Reuses existing services: LibraryService (in core/services/library_service.py)
"""

from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import date, timedelta

from core.models import (
    LibraryBook, LibraryBookCopy, LibraryCategory, LibraryBorrow,
    LibraryReturn, Student
)
from core.authz.drf import ModuleEnabled, HasPermission


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class LibraryCategorySerializer(serializers.ModelSerializer):
    """Serializer for LibraryCategory — book classifications."""
    class Meta:
        model = LibraryCategory
        fields = [
            'id', 'name', 'code', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LibraryBookSerializer(serializers.ModelSerializer):
    """Serializer for LibraryBook — books in the catalog."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    total_copies = serializers.SerializerMethodField()
    available_copies = serializers.SerializerMethodField()

    class Meta:
        model = LibraryBook
        fields = [
            'id', 'title', 'isbn', 'author', 'publisher', 'publication_year',
            'category', 'category_name', 'description', 'total_copies',
            'available_copies', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_copies(self, obj):
        """Count total copies of this book."""
        return obj.copies.count()

    def get_available_copies(self, obj):
        """Count available (not borrowed) copies."""
        return obj.copies.filter(condition='available').count()


class LibraryBookCopySerializer(serializers.ModelSerializer):
    """Serializer for LibraryBookCopy — individual book copies."""
    book_title = serializers.CharField(source='book.title', read_only=True)

    class Meta:
        model = LibraryBookCopy
        fields = [
            'id', 'book', 'book_title', 'barcode', 'condition',
            'acquisition_date', 'is_borrowed', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LibraryBorrowSerializer(serializers.ModelSerializer):
    """Serializer for LibraryBorrow — book checkouts."""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    book_title = serializers.CharField(source='copy.book.title', read_only=True)

    class Meta:
        model = LibraryBorrow
        fields = [
            'id', 'student', 'student_name', 'copy', 'book_title',
            'checkout_date', 'due_date', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'checkout_date', 'created_at', 'updated_at'
        ]


class LibraryReturnSerializer(serializers.ModelSerializer):
    """Serializer for LibraryReturn — book returns and overdue fines."""
    student_name = serializers.CharField(source='borrow.student.full_name', read_only=True)
    book_title = serializers.CharField(source='borrow.copy.book.title', read_only=True)
    days_overdue = serializers.SerializerMethodField()

    class Meta:
        model = LibraryReturn
        fields = [
            'id', 'borrow', 'student_name', 'book_title',
            'return_date', 'condition_on_return', 'days_overdue',
            'fine_amount', 'fine_paid', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'return_date', 'days_overdue', 'created_at', 'updated_at'
        ]

    def get_days_overdue(self, obj):
        """Calculate days overdue."""
        if obj.borrow.due_date <= obj.return_date:
            return 0
        return (obj.borrow.due_date - obj.return_date).days


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class LibraryCategoryViewSet(viewsets.ModelViewSet):
    """Book category management."""
    queryset = LibraryCategory.objects.all()
    serializer_class = LibraryCategorySerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("library"),
        HasPermission(read="library.books.view", write="library.books.manage"),
    ]
    module = "library"
    search_fields = ['name', 'code']
    ordering_fields = ['name']
    ordering = ['name']


class LibraryBookViewSet(viewsets.ModelViewSet):
    """
    Book catalog management.

    Covers:
    - List/filter books (by category, availability)
    - Book details with copy count
    - Search by title, author, ISBN
    """
    queryset = LibraryBook.objects.select_related('category').prefetch_related('copies')
    serializer_class = LibraryBookSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("library"),
        HasPermission(read="library.books.view", write="library.books.manage"),
    ]
    module = "library"
    filterset_fields = ['category']
    search_fields = ['title', 'author', 'isbn']
    ordering_fields = ['title', 'author']
    ordering = ['title']

    @extend_schema(description="Get books by category")
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Get books grouped by category with counts."""
        books = LibraryBook.objects.filter(tenant=request.tenant).values(
            'category__name'
        ).annotate(
            count=models.Count('id')
        ).order_by('category__name')
        return Response(books)


class LibraryBookCopyViewSet(viewsets.ModelViewSet):
    """
    Book copy management — individual copies.

    Covers:
    - Inventory tracking
    - Condition monitoring
    - Barcode management
    """
    queryset = LibraryBookCopy.objects.select_related('book')
    serializer_class = LibraryBookCopySerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("library"),
        HasPermission(read="library.books.view", write="library.books.manage"),
    ]
    module = "library"
    filterset_fields = ['book', 'condition', 'is_borrowed']
    search_fields = ['barcode', 'book__title']
    ordering_fields = ['book__title', 'condition']
    ordering = ['book__title']


class LibraryBorrowViewSet(viewsets.ModelViewSet):
    """
    Book borrowing management — checkouts.

    Covers:
    - Record book checkouts
    - Track due dates
    - List borrowed books
    """
    queryset = LibraryBorrow.objects.select_related('student', 'copy')
    serializer_class = LibraryBorrowSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("library"),
        HasPermission(read="library.borrow.view", write="library.borrow.manage"),
    ]
    module = "library"
    filterset_fields = ['student', 'copy__book']
    search_fields = ['student__full_name', 'copy__book__title']
    ordering_fields = ['checkout_date', 'due_date']
    ordering = ['-checkout_date']

    @extend_schema(
        description="Get student's currently borrowed books",
        parameters=[
            OpenApiParameter(name='student', required=True, description='Student ID'),
        ],
    )
    @action(detail=False, methods=['get'])
    def student_borrowed(self, request):
        """Get books currently borrowed by a student."""
        student_id = request.query_params.get('student')
        if not student_id:
            return Response({'error': 'student ID required'}, status=400)

        borrows = LibraryBorrow.objects.filter(
            student_id=student_id,
            return__isnull=True,  # Not yet returned
            tenant=request.tenant
        ).select_related('copy', 'student')

        return Response(LibraryBorrowSerializer(borrows, many=True).data)


class LibraryReturnViewSet(viewsets.ModelViewSet):
    """
    Book return management — checkins and overdue tracking.

    Covers:
    - Record book returns
    - Calculate overdue fines
    - Track return conditions
    """
    queryset = LibraryReturn.objects.select_related('borrow')
    serializer_class = LibraryReturnSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("library"),
        HasPermission(read="library.borrow.view", write="library.borrow.manage"),
    ]
    module = "library"
    filterset_fields = ['fine_paid', 'condition_on_return']
    search_fields = ['borrow__student__full_name', 'borrow__copy__book__title']
    ordering_fields = ['return_date']
    ordering = ['-return_date']

    @extend_schema(description="Get overdue books report")
    @action(detail=False, methods=['get'])
    def overdue_report(self, request):
        """Get report of overdue books (not yet returned, past due date)."""
        today = date.today()
        borrows = LibraryBorrow.objects.filter(
            due_date__lt=today,
            return__isnull=True,  # Not yet returned
            tenant=request.tenant
        ).select_related('student', 'copy')

        overdue = []
        for borrow in borrows:
            days_overdue = (today - borrow.due_date).days
            overdue.append({
                'student': borrow.student.full_name,
                'book': borrow.copy.book.title,
                'due_date': borrow.due_date,
                'days_overdue': days_overdue,
                'fine_estimate': days_overdue * 10,  # Example: 10 per day
            })

        return Response(overdue)

    @extend_schema(description="Get fine collection summary")
    @action(detail=False, methods=['get'])
    def fine_summary(self, request):
        """Get summary of fine collection."""
        returns = LibraryReturn.objects.filter(
            tenant=request.tenant
        ).aggregate(
            total_fines=models.Sum('fine_amount'),
            total_paid=models.Sum('fine_amount', filter=models.Q(fine_paid=True)),
            total_pending=models.Sum('fine_amount', filter=models.Q(fine_paid=False)),
        )

        return Response({
            'total_fines': returns['total_fines'] or 0,
            'total_paid': returns['total_paid'] or 0,
            'total_pending': returns['total_pending'] or 0,
        })


# Import models.Count and models.Q for aggregation
from django.db import models
