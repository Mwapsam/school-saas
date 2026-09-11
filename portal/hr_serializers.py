"""Serializers for the HR portal API.

Read serializers are thin ``ModelSerializer``s over the HR models; write
serializers validate the payloads the views hand to the service layer.
"""
from __future__ import annotations

from rest_framework import serializers

from core.models import (
    Employee, EmployeeContract, EmployeeDocument, EmployeeLeave,
    EmployeeQualification, EmploymentHistoryEvent, HRAuditLog, HRTask,
    EmployeeAttendance,
)


# ── Employee ────────────────────────────────────────────────────────────────

class EmployeeListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    department = serializers.CharField(source="employee_department.name", default=None, read_only=True)
    position = serializers.CharField(source="employee_position.name", default=None, read_only=True)
    gender_label = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id", "employee_number", "full_name", "first_name", "last_name",
            "email", "mobile_phone", "job_title", "department", "position",
            "is_teaching_staff", "employment_status", "status", "joining_date",
            "gender_label",
        ]

    def get_gender_label(self, obj):
        return "Male" if obj.gender else "Female"


class EmployeeDetailSerializer(EmployeeListSerializer):
    category = serializers.CharField(source="employee_category.name", default=None, read_only=True)
    grade = serializers.CharField(source="employee_grade.name", default=None, read_only=True)
    reporting_manager_name = serializers.CharField(
        source="reporting_manager.full_name", default=None, read_only=True
    )
    photo_url = serializers.SerializerMethodField()

    class Meta(EmployeeListSerializer.Meta):
        fields = EmployeeListSerializer.Meta.fields + [
            "middle_name", "date_of_birth", "national_id", "marital_status",
            "blood_group", "category", "grade", "reporting_manager_name",
            "home_address_line1", "home_address_line2", "home_city",
            "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relation", "next_of_kin_name", "next_of_kin_phone",
            "next_of_kin_relation", "qualification", "experience_year",
            "experience_month", "photo_url",
        ]

    def get_photo_url(self, obj):
        try:
            return obj.photo.url if obj.photo else None
        except Exception:
            return None


class EmployeeCreateSerializer(serializers.Serializer):
    """Minimum viable new-hire record — handed to
    ``EmployeeService.create_employee``."""

    employee_number = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    middle_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    joining_date = serializers.DateField()
    gender = serializers.BooleanField()
    job_title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    mobile_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    is_teaching_staff = serializers.BooleanField(required=False, default=False)
    employment_status = serializers.ChoiceField(
        choices=[c[0] for c in Employee.EMPLOYMENT_STATUS_CHOICES],
        required=False, default="active",
    )
    employee_department_id = serializers.UUIDField(required=False, allow_null=True)
    employee_position_id = serializers.UUIDField(required=False, allow_null=True)
    employee_category_id = serializers.UUIDField(required=False, allow_null=True)


class EmployeeUpdateSerializer(serializers.Serializer):
    """Whitelisted HR edits — handed straight to
    ``EmployeeService.update_employee``."""

    first_name = serializers.CharField(required=False)
    middle_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    mobile_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    job_title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    national_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    marital_status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    blood_group = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    home_address_line1 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    home_address_line2 = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    home_city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    emergency_contact_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    emergency_contact_relation = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    next_of_kin_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    next_of_kin_phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    next_of_kin_relation = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    employment_status = serializers.ChoiceField(
        choices=[c[0] for c in Employee.EMPLOYMENT_STATUS_CHOICES], required=False
    )
    is_teaching_staff = serializers.BooleanField(required=False)
    employee_department_id = serializers.UUIDField(required=False, allow_null=True)
    employee_position_id = serializers.UUIDField(required=False, allow_null=True)
    employee_category_id = serializers.UUIDField(required=False, allow_null=True)
    employee_grade_id = serializers.UUIDField(required=False, allow_null=True)
    reporting_manager_id = serializers.UUIDField(required=False, allow_null=True)


# ── Contract ────────────────────────────────────────────────────────────────

class ContractSerializer(serializers.ModelSerializer):
    days_remaining = serializers.IntegerField(read_only=True)
    contract_type_label = serializers.CharField(source="get_contract_type_display", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)

    class Meta:
        model = EmployeeContract
        fields = [
            "id", "employee_id", "employee_name", "employee_number",
            "contract_type", "contract_type_label", "start_date", "end_date",
            "probation_end_date", "salary_review_date", "renewal_status",
            "notes", "days_remaining", "supersedes_id", "created_at",
        ]


class ContractWriteSerializer(serializers.Serializer):
    contract_type = serializers.ChoiceField(choices=[c[0] for c in EmployeeContract.CONTRACT_TYPE_CHOICES])
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)
    probation_end_date = serializers.DateField(required=False, allow_null=True)
    salary_review_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ContractRenewSerializer(serializers.Serializer):
    new_start_date = serializers.DateField()
    new_end_date = serializers.DateField(required=False, allow_null=True)
    contract_type = serializers.ChoiceField(
        choices=[c[0] for c in EmployeeContract.CONTRACT_TYPE_CHOICES], required=False
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ContractDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=["renewal_pending", "not_renewed", "expiring_soon", "active"]
    )


# ── Documents / qualifications ──────────────────────────────────────────────

class EmployeeDocumentSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeDocument
        fields = [
            "id", "employee_id", "document_type", "original_filename", "note",
            "issued_date", "expiry_date", "uploaded_at", "status", "file_url",
        ]

    def get_status(self, obj):
        return obj.status()

    def get_file_url(self, obj):
        try:
            return obj.file.url if obj.file else None
        except Exception:
            return None


class DocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.CharField()
    file = serializers.FileField()
    issued_date = serializers.DateField(required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class QualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeQualification
        fields = [
            "id", "employee_id", "qualification_type", "name", "institution",
            "year_obtained", "is_highest", "document_id",
        ]


class QualificationWriteSerializer(serializers.Serializer):
    qualification_type = serializers.ChoiceField(
        choices=[c[0] for c in EmployeeQualification.QUALIFICATION_TYPE_CHOICES],
        default="academic",
    )
    name = serializers.CharField()
    institution = serializers.CharField(required=False, allow_blank=True, default="")
    year_obtained = serializers.IntegerField(required=False, allow_null=True)
    is_highest = serializers.BooleanField(required=False, default=False)


# ── History / audit ────────────────────────────────────────────────────────

class HistoryEventSerializer(serializers.ModelSerializer):
    event_type_label = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = EmploymentHistoryEvent
        fields = [
            "id", "employee_id", "event_type", "event_type_label",
            "effective_date", "old_value", "new_value", "note", "created_at",
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HRAuditLog
        fields = [
            "id", "actor_label", "action", "target_type", "target_id",
            "field", "old_value", "new_value", "created_at",
        ]


# ── Leave (HR view) ────────────────────────────────────────────────────────

class HRLeaveSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    leave_type_name = serializers.SerializerMethodField()
    days = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeLeave
        fields = [
            "id", "employee_id", "employee_name", "employee_number",
            "leave_type_name", "start_date", "end_date", "days", "reason",
            "status", "supervisor_status", "supervisor_remark", "supervisor_acted_at",
            "hr_status", "hr_remark", "hr_acted_at", "document",
        ]

    def get_leave_type_name(self, obj):
        return getattr(obj.leave_type, "name", obj.leave_type_legacy or "Leave")

    def get_days(self, obj):
        return (obj.end_date - obj.start_date).days + 1


class LeaveDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    remark = serializers.CharField(required=False, allow_blank=True, default="")


class LeaveApplySerializer(serializers.Serializer):
    leave_type_id = serializers.UUIDField(required=False, allow_null=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField()
    document = serializers.FileField(required=False, allow_null=True)


# ── Attendance ─────────────────────────────────────────────────────────────

class AttendanceRowSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EmployeeAttendance
        fields = [
            "id", "employee_id", "employee_name", "date", "status", "status_label",
            "clock_in", "clock_out", "hours_worked", "late_minutes", "remarks",
        ]


class AttendanceMarkSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()
    date = serializers.DateField()
    status = serializers.ChoiceField(choices=[c[0] for c in EmployeeAttendance.STATUS_CHOICES])
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


# ── HR tasks ───────────────────────────────────────────────────────────────

class HRTaskSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", default=None, read_only=True)

    class Meta:
        model = HRTask
        fields = [
            "id", "title", "description", "category", "status", "due_date",
            "employee_id", "employee_name", "source", "created_at", "completed_at",
        ]


class HRTaskWriteSerializer(serializers.Serializer):
    title = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    category = serializers.ChoiceField(
        choices=[c[0] for c in HRTask.CATEGORY_CHOICES], required=False
    )
    status = serializers.ChoiceField(
        choices=[c[0] for c in HRTask.STATUS_CHOICES], required=False
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    employee_id = serializers.UUIDField(required=False, allow_null=True)
