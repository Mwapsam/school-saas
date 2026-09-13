"""
Admissions domain serializers — student applications and inquiries.

Pattern: All serializers inherit from TenantAwareSerializer + ServiceSerializerMixin
for model-based serializers. Write-only input serializers follow ServiceSerializerMixin
to ensure service validation is applied.

This ensures:
1. Tenant context is properly passed to services
2. Service exceptions are translated to DRF errors
3. Validation logic is centralized in the service layer
"""

from datetime import date
from rest_framework import serializers
from core.models import AdmissionApplication
from core.serializers.base import TenantAwareSerializer, ServiceSerializerMixin
from core.services.admission_service import AdmissionService


class AdmissionApplicationSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for AdmissionApplication — student applications to the school.

    Delegates to AdmissionService for validation of applications. Includes
    read-only nested course name for context. Application number is auto-generated.

    Pattern:
    - Read: List/retrieve applications with course context
    - Create: Via AdmissionService, validates date_of_birth and required fields
    - Update: Via AdmissionService
    - Delete: Mark as withdrawn or remove
    - Approve/Reject: Via service workflow actions
    """
    service_class = AdmissionService
    course_name = serializers.CharField(source='course_applied.course_name', read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            'id', 'application_number', 'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'course_applied', 'course_name',
            'guardian_name', 'guardian_phone', 'guardian_email', 'address',
            'application_date', 'status', 'remarks',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'application_number', 'application_date',
            'created_at', 'updated_at'
        ]

    def validate_date_of_birth(self, value):
        """Ensure student is of reasonable age."""
        if value and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value

    def _service_create(self, service, validated_data):
        """Delegate AdmissionApplication creation to AdmissionService"""
        instance = AdmissionApplication.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate AdmissionApplication update to AdmissionService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AdmissionApplicationBatchAssignmentSerializer(ServiceSerializerMixin, serializers.Serializer):
    """
    Serializer for assigning admitted applications to batches.

    This is a write-only operation serializer (not model-based). It takes
    application_id and batch_id, and delegates the assignment logic to
    AdmissionService.assign_to_batch().

    Pattern:
    - Input validation: application_id and batch_id are valid UUIDs
    - Service validation: AdmissionService checks permissions, status, batch compatibility
    - Exceptions: Translated to DRF errors (e.g., "already assigned", "not admitted")
    """
    service_class = AdmissionService
    application_id = serializers.UUIDField()
    batch_id = serializers.UUIDField()
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Validate application and batch IDs are valid"""
        # Further validation done by service
        return data

    def _service_create(self, service, validated_data):
        """This serializer doesn't create instances — it triggers a service action"""
        # The ViewSet will call service.assign_to_batch(application_id, batch_id)
        # and return the result, not the serializer output
        raise NotImplementedError("Use ViewSet action to call service.assign_to_batch()")

    def _service_update(self, service, instance, validated_data):
        """Not applicable for this write-only serializer"""
        raise NotImplementedError("Not applicable for write-only serializer")
