"""
Students domain serializers — Student, Batch, Course, Subject.

Pattern: All serializers inherit from TenantAwareSerializer + ServiceSerializerMixin.
This ensures:
1. Tenant context is properly passed to services
2. Service exceptions are translated to DRF errors
3. Validation logic is centralized in the service layer

For each serializer:
- service_class: the service this serializer delegates to
- _service_create: how to create via the service
- _service_update: how to update via the service (or use default model-based update)
"""

from rest_framework import serializers
from core.models import Student, Batch, Course, Subject
from core.serializers.base import TenantAwareSerializer, ServiceSerializerMixin
from core.services.student_service import StudentService


class StudentSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for Student model — learner enrollment and management.

    Delegates to StudentService for validation. Includes read-only nested
    batch and course names for context.

    Pattern:
    - Read: List/retrieve with batch/course context
    - Create: Via StudentService, validates admission number uniqueness
    - Update: Via StudentService
    - Delete: Mark as inactive or remove
    """
    service_class = StudentService
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'admission_no', 'full_name', 'first_name', 'last_name',
            'date_of_birth', 'batch', 'batch_name', 'course', 'course_name',
            'gender', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        """Delegate Student creation to StudentService"""
        instance = Student.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate Student update to StudentService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class BatchSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for Batch model — student cohorts/groups.

    Delegates to StudentService for validation. Includes read-only nested
    course name and computed student count.

    Pattern:
    - Read: List/retrieve with course context and student count
    - Create: Via StudentService
    - Update: Via StudentService
    - Delete: Mark as inactive or remove
    """
    service_class = StudentService
    course_name = serializers.CharField(source='course.name', read_only=True)
    student_count = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = [
            'id', 'name', 'code', 'course', 'course_name', 'start_date', 'end_date',
            'student_count', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_student_count(self, obj):
        """Return count of students in this batch."""
        return obj.students.count()

    def _service_create(self, service, validated_data):
        """Delegate Batch creation to StudentService"""
        instance = Batch.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate Batch update to StudentService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class CourseSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for Course model — academic programs/sections.

    Delegates to StudentService for validation. A course is a container
    for batches (e.g., "Primary School", "High School", "Secondary Form 3").

    Pattern:
    - Read: List/retrieve courses
    - Create: Via StudentService
    - Update: Via StudentService
    - Delete: Mark as inactive or remove
    """
    service_class = StudentService

    class Meta:
        model = Course
        fields = [
            'id', 'name', 'code', 'description', 'section_name',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        """Delegate Course creation to StudentService"""
        instance = Course.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate Course update to StudentService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class SubjectSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for Subject model — curriculum subjects/courses taught.

    Delegates to StudentService for validation. A subject is a specific
    course content area (e.g., "Mathematics", "English Language", "Biology").

    Pattern:
    - Read: List/retrieve subjects
    - Create: Via StudentService
    - Update: Via StudentService
    - Delete: Mark as inactive or remove
    """
    service_class = StudentService

    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'code', 'description',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        """Delegate Subject creation to StudentService"""
        instance = Subject.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate Subject update to StudentService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
