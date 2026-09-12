"""
Batch assignment and student conversion DRF serializers
"""
from rest_framework import serializers
from core.models import ExtendedAdmissionApplication, Batch, BatchStudent, Student
from .base import TenantAwareSerializer


class BatchAssignmentApplicationSerializer(TenantAwareSerializer):
    """
    Serializer for applications ready for batch assignment
    """
    full_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id', 'application_number', 'first_name', 'last_name', 'full_name',
            'date_of_birth', 'email', 'phone', 'mobile', 'status', 'status_display',
            'academic_year', 'course_applied', 'application_date'
        ]
        read_only_fields = ['id', 'application_number', 'application_date', 'full_name', 'status_display']

    def get_full_name(self, obj):
        return obj.full_name


class BatchSerializer(TenantAwareSerializer):
    """
    Simple Batch serializer for dropdown
    """

    class Meta:
        model = Batch
        fields = ['id', 'name', 'section_name', 'grade_name']
        read_only_fields = ['id']


class SingleAssignmentSerializer(serializers.Serializer):
    """
    Serializer for single application batch assignment
    """
    application_id = serializers.UUIDField()
    batch_id = serializers.UUIDField()
    roll_number = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        """Validate that application and batch exist and are valid"""
        application_id = attrs.get('application_id')
        batch_id = attrs.get('batch_id')
        tenant = self.context.get('tenant')

        if not tenant:
            raise serializers.ValidationError("Tenant context required")

        try:
            application = ExtendedAdmissionApplication.objects.get(
                id=application_id,
                tenant=tenant,
                status__in=['approved', 'admitted']
            )
        except ExtendedAdmissionApplication.DoesNotExist:
            raise serializers.ValidationError(f"Application not found or not in approved/admitted status")

        try:
            batch = Batch.objects.get(
                id=batch_id,
                tenant=tenant,
                is_deleted=False,
                is_active=True
            )
        except Batch.DoesNotExist:
            raise serializers.ValidationError("Batch not found or not active")

        attrs['application'] = application
        attrs['batch'] = batch
        return attrs


class BulkAssignmentSerializer(serializers.Serializer):
    """
    Serializer for bulk batch assignment
    """

    class AssignmentItem(serializers.Serializer):
        application_id = serializers.UUIDField()
        batch_id = serializers.UUIDField()
        roll_number = serializers.CharField(required=False, allow_blank=True)

    assignments = AssignmentItem(many=True)

    def validate_assignments(self, value):
        """Validate assignments list"""
        if not value:
            raise serializers.ValidationError("Assignments list cannot be empty")
        if len(value) > 100:
            raise serializers.ValidationError("Cannot assign more than 100 applications at once")
        return value


class BatchStudentSerializer(TenantAwareSerializer):
    """
    Serializer for batch-student assignment result
    """
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True)

    class Meta:
        model = BatchStudent
        fields = [
            'id', 'student_id', 'student_name', 'batch_id', 'batch_name',
            'roll_number', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'student_id', 'batch_id', 'created_at']


class AssignmentResultSerializer(serializers.Serializer):
    """
    Serializer for assignment operation result
    """
    success = serializers.BooleanField()
    message = serializers.CharField()
    student_id = serializers.UUIDField(required=False, allow_null=True)
    batch_student_id = serializers.UUIDField(required=False, allow_null=True)
    application_id = serializers.UUIDField(required=False, allow_null=True)


class BulkAssignmentResultSerializer(serializers.Serializer):
    """
    Serializer for bulk assignment results
    """
    successful = serializers.IntegerField()
    failed = serializers.IntegerField()
    errors = serializers.ListField(child=serializers.CharField())


class AdmissionStatsSerializer(serializers.Serializer):
    """
    Serializer for admission statistics
    """
    total_applications = serializers.IntegerField()
    approved_applications = serializers.IntegerField()
    admitted_applications = serializers.IntegerField()
    rejected_applications = serializers.IntegerField()
    pending_review = serializers.IntegerField()
    students_admitted_total = serializers.IntegerField()
    batches_available = serializers.IntegerField()


class DiagnosticsResultSerializer(serializers.Serializer):
    """
    Serializer for admission system diagnostics
    """
    school_code = serializers.CharField()
    school_name = serializers.CharField()
    ready_for_admissions = serializers.BooleanField()
    missing_requirements = serializers.ListField(child=serializers.CharField())
    warnings = serializers.ListField(child=serializers.CharField())
    data_counts = serializers.DictField(child=serializers.IntegerField())
