"""
Library domain serializers — library configuration, staff, and books.

Pattern: All serializers inherit from TenantAwareSerializer + ServiceSerializerMixin.
This ensures:
1. Tenant context is properly passed to services
2. Service exceptions are translated to DRF errors
3. Validation logic is centralized in the service layer
"""

from rest_framework import serializers
from core.models import Library, LibraryStaff, Book
from core.serializers.base import TenantAwareSerializer, ServiceSerializerMixin


class LibrarySerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for Library — library configuration and settings.

    Each school can have one or more libraries. This represents the library
    configuration including name, location, and active status.

    Pattern:
    - Read: List/retrieve library configuration
    - Create: Via service
    - Update: Via service
    - Delete: Deactivate or remove library
    """
    service_class = None  # Will use LibraryService when available

    class Meta:
        model = Library
        fields = [
            'id', 'name', 'code', 'description',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = Library.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class LibraryStaffSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for LibraryStaff — librarians, assistants, and library support staff.

    Links library staff to their employee records. Includes read-only nested
    employee name/email and library name for context.

    Pattern:
    - Read: List/retrieve library staff
    - Create: Via service
    - Update: Via service
    - Delete: Remove staff assignment
    """
    service_class = None  # Will use LibraryService when available
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_email = serializers.EmailField(source='employee.email', read_only=True)
    library_name = serializers.CharField(source='library.name', read_only=True)

    class Meta:
        model = LibraryStaff
        fields = [
            'id', 'employee', 'employee_name', 'employee_email',
            'library', 'library_name', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = LibraryStaff.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class BookSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for Book — library catalog entries.

    Represents individual book records in the library system. Tracks title, author,
    ISBN, copy count, availability, location, and category.

    Pattern:
    - Read: List/retrieve books
    - Create: Via service
    - Update: Via service (update availability count, location, etc.)
    - Delete: Remove book from catalog
    """
    service_class = None  # Will use LibraryService when available
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Book
        fields = [
            'id', 'title', 'author', 'isbn', 'book_number', 'category', 'category_name',
            'location', 'total_copies', 'available_copies', 'price', 'book_type',
            'school_level', 'barcode', 'library', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = Book.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
