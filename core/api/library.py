"""
Library domain API — library management.

Covers:
- Library configuration (library name, location, contact)
- Library staff (librarians, assistants)
- Book catalog (title/author/copies/availability)

Note: Borrowing/returns (BookMovement) still requires additional API work for future implementation.

Reuses existing services: See core/services/
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.models import Library, LibraryStaff, Book
from core.authz.drf import ModuleEnabled, HasPermission
from core.api.base import TenantAwareViewSet
from core.serializers.library_serializers import LibrarySerializer, LibraryStaffSerializer, BookSerializer


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class LibraryViewSet(TenantAwareViewSet):
    """
    Library management — manage library configuration.

    Covers:
    - List/create/update/delete library records
    - Filter by active status
    - Manage library hours and settings
    """
    queryset = Library.objects.all()
    serializer_class = LibrarySerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="library.config.view", write="library.config.manage"),
    ]
    module = "library"
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class LibraryStaffViewSet(TenantAwareViewSet):
    """
    Library staff management — manage librarians and assistants.

    Covers:
    - List/create/update/delete staff
    - Filter by staff type or active status
    - Search by name or email
    """
    queryset = LibraryStaff.objects.all()
    serializer_class = LibraryStaffSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="library.staff.view", write="library.staff.manage"),
    ]
    module = "library"
    filterset_fields = ['library', 'is_active']
    search_fields = ['employee__first_name', 'employee__last_name', 'employee__email']
    ordering_fields = ['employee__last_name', 'created_at']
    ordering = ['employee__last_name']

    def get_queryset(self):
        return super().get_queryset().select_related('employee', 'library')


class BookViewSet(TenantAwareViewSet):
    """
    Book catalog management.

    Covers:
    - List/create/update/delete book records
    - Filter by category, book type, school level, or library
    - Search by title, author, ISBN, or book number

    Note: borrowing/returns (checkout workflow) is not yet exposed here —
    only catalog CRUD. See BookMovement model for future circulation API.
    """
    queryset = Book.objects.select_related('category', 'library').all()
    serializer_class = BookSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="library.view", write="library.manage"),
    ]
    module = "library"
    filterset_fields = ['category', 'book_type', 'school_level', 'library']
    search_fields = ['title', 'author', 'isbn', 'book_number']
    ordering_fields = ['title', 'author', 'created_at']
    ordering = ['title']
