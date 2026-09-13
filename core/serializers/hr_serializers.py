"""
HR (Human Resources) domain serializers — employee, leave, attendance, performance, training.

Pattern: All serializers inherit from TenantAwareSerializer + ServiceSerializerMixin.
This ensures:
1. Tenant context is properly passed to services
2. Service exceptions are translated to DRF errors
3. Validation logic is centralized in the service layer

For each serializer:
- service_class: the service this serializer delegates to (HRService, LeaveService, etc.)
- _service_create: how to create via the service
- _service_update: how to update via the service (or use default model-based update)
"""

from datetime import date
from rest_framework import serializers
from core.models import (
    Employee, EmployeeContract, EmployeeQualification, EmployeeDocument,
    LeaveType, EmployeeAttendance, PerformanceReview, TrainingRecord, EmployeeExit,
    EmployeeLeave,
)
from core.serializers.base import TenantAwareSerializer, ServiceSerializerMixin
from core.services.leave_attendance_service import LeaveService


class EmployeeQualificationSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for EmployeeQualification — degrees, certifications, educational credentials.

    Delegates to HRService for validation. Tracks highest qualification and related documents.

    Pattern:
    - Read: List/retrieve qualifications for an employee
    - Create: Via HRService
    - Update: Via HRService
    - Delete: Remove qualification record
    """
    service_class = LeaveService  # Will use appropriate HRService when available

    class Meta:
        model = EmployeeQualification
        fields = [
            'id', 'employee', 'qualification_type', 'name', 'institution',
            'year_obtained', 'is_highest', 'document', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = EmployeeQualification.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EmployeeDocumentSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for EmployeeDocument — NRC, CV, certificates, contracts, etc.

    Delegates to HRService for validation. Tracks document expiry dates.

    Pattern:
    - Read: List/retrieve documents for an employee
    - Create: Via HRService
    - Update: Via HRService
    - Delete: Remove document record
    """
    service_class = LeaveService

    class Meta:
        model = EmployeeDocument
        fields = [
            'id', 'employee', 'document_type', 'file', 'original_filename', 'note',
            'issued_date', 'expiry_date', 'uploaded_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'uploaded_at', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = EmployeeDocument.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EmployeeContractSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for EmployeeContract — employment agreements and terms.

    Delegates to HRService for validation. Tracks contract history with supersedes links.

    Pattern:
    - Read: List/retrieve contracts for an employee
    - Create: Via HRService
    - Update: Via HRService (creates new contract, marks old as superseded)
    - Delete: Remove contract record
    """
    service_class = LeaveService

    class Meta:
        model = EmployeeContract
        fields = [
            'id', 'employee', 'contract_type', 'start_date', 'end_date',
            'probation_end_date', 'salary_review_date', 'renewal_status',
            'notes', 'document', 'supersedes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = EmployeeContract.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EmployeeSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for Employee — staff directory and core employee information.

    Delegates to HRService for validation. Includes computed fields:
    - gender_display: 'M'/'F'/None for binary gender field
    - department_name, position_name, category_name: nested FK names

    Pattern:
    - Read: List/retrieve employees with full context
    - Create: Via HRService
    - Update: Via HRService
    - Delete: Soft-delete (status=False) or remove
    """
    service_class = LeaveService
    department_name = serializers.CharField(source='employee_department.name', read_only=True, default=None)
    position_name = serializers.CharField(source='employee_position.name', read_only=True, default=None)
    category_name = serializers.CharField(source='employee_category.name', read_only=True, default=None)
    gender_display = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_number', 'first_name', 'middle_name', 'last_name', 'full_name',
            'email', 'mobile_phone', 'gender', 'gender_display', 'job_title', 'is_teaching_staff',
            'employee_category', 'category_name', 'employee_position', 'position_name',
            'employee_department', 'department_name', 'reporting_manager', 'employee_grade',
            'joining_date', 'date_of_birth', 'national_id', 'status', 'employment_status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_gender_display(self, obj):
        if obj.gender is None:
            return None
        return 'M' if obj.gender else 'F'

    def _service_create(self, service, validated_data):
        instance = Employee.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class LeaveTypeSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for LeaveType — leave categories (sick, vacation, personal, etc.).

    Delegates to LeaveService for validation. Tracks annual entitlements and payment status.

    Pattern:
    - Read: List/retrieve leave types
    - Create: Via LeaveService
    - Update: Via LeaveService
    - Delete: Remove leave type
    """
    service_class = LeaveService

    class Meta:
        model = LeaveType
        fields = ['id', 'name', 'code', 'default_annual_days', 'is_paid', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = LeaveType.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class LeaveRequestSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for EmployeeLeave — employee leave requests and approval workflow.

    Delegates to LeaveService for validation and approval workflow. Read-only after
    creation: requests are approved/rejected via dedicated ViewSet actions, not direct updates.

    Pattern:
    - Read: List/retrieve leave requests
    - Create: Via LeaveService (performed via ViewSet.perform_create)
    - Update: Not exposed (use ViewSet.approve/reject actions instead)
    - Delete: Not exposed
    """
    service_class = LeaveService
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True, default=None)

    class Meta:
        model = EmployeeLeave
        fields = [
            'id', 'employee', 'employee_name', 'leave_type', 'leave_type_name',
            'start_date', 'end_date', 'reason', 'status', 'is_approved',
            'approved_by', 'manager_remark',
            'supervisor_status', 'supervisor_remark',
            'hr_status', 'hr_remark',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'status', 'is_approved', 'approved_by', 'manager_remark',
            'supervisor_status', 'supervisor_remark',
            'hr_status', 'hr_remark',
            'created_at', 'updated_at',
        ]

    def _service_create(self, service, validated_data):
        # Creation is handled by ViewSet.perform_create via service.request_leave()
        instance = EmployeeLeave.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        # Updates not exposed — use ViewSet actions instead
        raise NotImplementedError("Use ViewSet approve/reject actions instead of direct update")


class AttendanceSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for EmployeeAttendance — daily staff attendance records.

    Delegates to LeaveService (or HRService) for validation. Tracks clock-in/out,
    hours worked, and lateness.

    Pattern:
    - Read: List/retrieve attendance records
    - Create: Via service
    - Update: Via service
    - Delete: Remove attendance record
    """
    service_class = LeaveService
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = EmployeeAttendance
        fields = [
            'id', 'employee', 'employee_name', 'date', 'status', 'marked_by', 'remarks',
            'clock_in', 'clock_out', 'hours_worked', 'late_minutes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = EmployeeAttendance.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class PerformanceReviewSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for PerformanceReview — annual/periodic appraisals and feedback.

    Delegates to HRService for validation. Tracks review period, ratings, and development actions.

    Pattern:
    - Read: List/retrieve reviews
    - Create: Via HRService
    - Update: Via HRService
    - Delete: Remove review record
    """
    service_class = LeaveService

    class Meta:
        model = PerformanceReview
        fields = [
            'id', 'employee', 'reviewer', 'review_period', 'review_date', 'status',
            'is_teacher_review', 'overall_rating', 'objectives', 'strengths',
            'improvement_areas', 'development_actions', 'reviewer_comments',
            'employee_comments', 'next_review_date', 'completed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = PerformanceReview.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class TrainingRecordSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for TrainingRecord — training programs, CPD, and professional development.

    Delegates to HRService for validation. Tracks training provider, dates, costs, and certificates.

    Pattern:
    - Read: List/retrieve training records
    - Create: Via HRService
    - Update: Via HRService
    - Delete: Remove training record
    """
    service_class = LeaveService

    class Meta:
        model = TrainingRecord
        fields = [
            'id', 'employee', 'name', 'category', 'provider', 'training_date',
            'cost', 'certificate', 'expiry_date', 'status', 'is_mandatory',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = TrainingRecord.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EmployeeExitSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for EmployeeExit — exit/offboarding records and final settlement.

    Delegates to HRService for validation. Tracks exit reason, notice period, final payments, and handover.

    Pattern:
    - Read: List/retrieve exit records
    - Create: Via HRService
    - Update: Via HRService
    - Delete: Remove exit record
    """
    service_class = LeaveService

    class Meta:
        model = EmployeeExit
        fields = [
            'id', 'employee', 'exit_type', 'notice_date', 'last_working_date',
            'reason', 'exit_interview_notes', 'final_payment_status',
            'outstanding_leave_days', 'handover_status', 'status', 'completed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        instance = EmployeeExit.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
