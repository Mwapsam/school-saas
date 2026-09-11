"""
Library domain API — library management.

Covers:
- Library configuration (library name, location, contact)
- Library staff (librarians, assistants)

Note: Full library circulation system (book catalog, borrowing, returns) requires additional models for future implementation.

Reuses existing services: See core/services/
"""

from rest_framework import viewsets, serializers
from rest_framework.permissions import IsAuthenticated

from core.models import Library, LibraryStaff
from core.authz.drf import ModuleEnabled, HasPermission


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class LibrarySerializer(serializers.ModelSerializer):
    """Serializer for Library — library configuration."""
    class Meta:
        model = Library
        fields = [
            'id', 'name', 'location', 'phone', 'email', 'opening_time',
            'closing_time', 'max_book_checkout_duration', 'max_books_per_checkout',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LibraryStaffSerializer(serializers.ModelSerializer):
    """Serializer for LibraryStaff — librarians and library assistants."""
    class Meta:
        model = LibraryStaff
        fields = [
            'id', 'name', 'staff_type', 'phone', 'email', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class LibraryViewSet(viewsets.ModelViewSet):
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
    search_fields = ['name', 'location']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class LibraryStaffViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['staff_type', 'is_active']
    search_fields = ['name', 'email']
    ordering_fields = ['name', 'staff_type', 'created_at']
    ordering = ['name']
