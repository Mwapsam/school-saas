from rest_framework import serializers
from django.utils import timezone
from ..models import (
    ApplicantEnquiry,
    ApplicantEnquiryStage,
    ApplicantEnquiryFormField,
    ApplicantEnquiryFormFieldOption,
    EnquiryStageLog,
    EnquiryStageLogNote,
    EnquiryFollowUp,
    Course,
    AcademicYear,
    Employee,
)


class ApplicantEnquiryStageSerializer(serializers.ModelSerializer):
    """Serializer for enquiry stages"""

    class Meta:
        model = ApplicantEnquiryStage
        fields = ['id', 'name', 'is_default', 'priority', 'color', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class ApplicantEnquiryFormFieldOptionSerializer(serializers.ModelSerializer):
    """Serializer for form field options"""

    class Meta:
        model = ApplicantEnquiryFormFieldOption
        fields = ['id', 'option_value', 'option_text', 'priority']


class ApplicantEnquiryFormFieldSerializer(serializers.ModelSerializer):
    """Serializer for form field configuration"""
    options = ApplicantEnquiryFormFieldOptionSerializer(many=True, read_only=True)

    class Meta:
        model = ApplicantEnquiryFormField
        fields = [
            'id', 'category', 'field_name', 'display_text', 'field_type',
            'is_active', 'is_mandatory', 'is_additional', 'priority',
            'placeholder_text', 'help_text', 'options', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class CourseBasicSerializer(serializers.ModelSerializer):
    """Basic course serializer for enquiry references"""

    class Meta:
        model = Course
        fields = ['id', 'name', 'code']


class AcademicYearBasicSerializer(serializers.ModelSerializer):
    """Basic academic year serializer for enquiry references"""

    class Meta:
        model = AcademicYear
        fields = ['id', 'name', 'start_date', 'end_date']


class EmployeeBasicSerializer(serializers.ModelSerializer):
    """Basic employee serializer for counselor references"""

    class Meta:
        model = Employee
        fields = ['id', 'first_name', 'last_name', 'email']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['full_name'] = f"{instance.first_name} {instance.last_name}"
        return data


class EnquiryStageLogNoteSerializer(serializers.ModelSerializer):
    """Serializer for enquiry stage log notes"""
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = EnquiryStageLogNote
        fields = [
            'id', 'notes', 'follow_up_date', 'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class EnquiryStageLogSerializer(serializers.ModelSerializer):
    """Serializer for enquiry stage logs"""
    stage_name = serializers.CharField(source='stage.name', read_only=True)
    changed_by_name = serializers.CharField(source='changed_by.full_name', read_only=True)
    notes = EnquiryStageLogNoteSerializer(many=True, read_only=True)

    class Meta:
        model = EnquiryStageLog
        fields = [
            'id', 'stage', 'stage_name', 'changed_by', 'changed_by_name',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class EnquiryFollowUpSerializer(serializers.ModelSerializer):
    """Serializer for enquiry follow-ups"""
    follow_up_type_display = serializers.CharField(source='get_follow_up_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)

    class Meta:
        model = EnquiryFollowUp
        fields = [
            'id', 'follow_up_type', 'follow_up_type_display', 'scheduled_date',
            'status', 'status_display', 'assigned_to', 'assigned_to_name',
            'notes', 'completion_notes', 'completed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_scheduled_date(self):
        scheduled_date = self.validated_data.get('scheduled_date')
        if scheduled_date and scheduled_date < timezone.now():
            raise serializers.ValidationError("Follow-up date cannot be in the past.")
        return scheduled_date


class ApplicantEnquiryListSerializer(serializers.ModelSerializer):
    """Serializer for enquiry list view"""
    course_name = serializers.CharField(source='course.name', read_only=True)
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    stage_name = serializers.CharField(source='stage.name', read_only=True)
    stage_color = serializers.CharField(source='stage.color', read_only=True)
    counselor_name = serializers.CharField(source='counselor.full_name', read_only=True)

    class Meta:
        model = ApplicantEnquiry
        fields = [
            'id', 'enquiry_number', 'first_name', 'last_name', 'email', 'phone',
            'enquired_date', 'course', 'course_name', 'academic_year', 'academic_year_name',
            'stage', 'stage_name', 'stage_color', 'counselor', 'counselor_name',
            'is_processed', 'is_rejected', 'is_viewed', 'created_at'
        ]
        read_only_fields = ['enquiry_number', 'created_at']


class ApplicantEnquiryDetailSerializer(serializers.ModelSerializer):
    """Serializer for enquiry detail view"""
    course = CourseBasicSerializer(read_only=True)
    academic_year = AcademicYearBasicSerializer(read_only=True)
    stage = ApplicantEnquiryStageSerializer(read_only=True)
    counselor = EmployeeBasicSerializer(read_only=True)
    stage_logs = EnquiryStageLogSerializer(many=True, read_only=True)
    follow_ups = EnquiryFollowUpSerializer(many=True, read_only=True)

    class Meta:
        model = ApplicantEnquiry
        fields = [
            # Basic info
            'id', 'enquiry_number', 'enquired_date', 'course', 'academic_year', 'stage',
            # Student information
            'first_name', 'last_name', 'date_of_birth', 'email', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            # Guardian information
            'guardian_first_name', 'guardian_last_name', 'guardian_relation',
            'guardian_email', 'guardian_phone', 'guardian_address_line1', 'guardian_address_line2',
            'guardian_occupation', 'guardian_income', 'guardian_education',
            # Office information
            'counselor', 'source_of_info', 'remarks',
            # Status tracking
            'is_processed', 'is_rejected', 'is_viewed', 'is_email_enabled',
            # Additional data
            'additional_data',
            # Related data
            'stage_logs', 'follow_ups',
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = ['enquiry_number', 'created_at', 'updated_at']


class ApplicantEnquiryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating enquiries"""

    class Meta:
        model = ApplicantEnquiry
        fields = [
            # Basic info
            'course', 'academic_year', 'enquired_date',
            # Student information
            'first_name', 'last_name', 'date_of_birth', 'email', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            # Guardian information
            'guardian_first_name', 'guardian_last_name', 'guardian_relation',
            'guardian_email', 'guardian_phone', 'guardian_address_line1', 'guardian_address_line2',
            'guardian_occupation', 'guardian_income', 'guardian_education',
            # Office information
            'counselor', 'source_of_info', 'remarks',
            # Additional data
            'additional_data',
        ]

    def validate_email(self, value):
        """Validate email uniqueness within tenant"""
        if value:
            tenant = self.context['request'].tenant
            existing = ApplicantEnquiry.objects.filter(
                tenant=tenant,
                email=value
            )
            if self.instance:
                existing = existing.exclude(id=self.instance.id)

            if existing.exists():
                raise serializers.ValidationError("An enquiry with this email already exists.")
        return value

    def validate(self, data):
        """Cross-field validation"""
        email = data.get('email')
        phone = data.get('phone')

        if not email and not phone:
            raise serializers.ValidationError({
                'non_field_errors': ["Please provide either email or phone number."]
            })

        return data

    def create(self, validated_data):
        """Create enquiry with tenant and default stage"""
        tenant = self.context['request'].tenant
        validated_data['tenant'] = tenant

        # Set default stage if not provided
        if not validated_data.get('stage'):
            default_stage = ApplicantEnquiryStage.objects.filter(
                tenant=tenant,
                is_default=True
            ).first()
            if default_stage:
                validated_data['stage'] = default_stage

        enquiry = super().create(validated_data)

        # Create initial stage log
        if enquiry.stage:
            EnquiryStageLog.objects.create(
                tenant=tenant,
                enquiry=enquiry,
                stage=enquiry.stage
            )

        return enquiry


class ApplicantEnquiryUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating enquiries"""

    class Meta:
        model = ApplicantEnquiry
        fields = [
            # Basic info
            'course', 'academic_year', 'stage',
            # Student information
            'first_name', 'last_name', 'date_of_birth', 'email', 'phone',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code',
            # Guardian information
            'guardian_first_name', 'guardian_last_name', 'guardian_relation',
            'guardian_email', 'guardian_phone', 'guardian_address_line1', 'guardian_address_line2',
            'guardian_occupation', 'guardian_income', 'guardian_education',
            # Office information
            'counselor', 'source_of_info', 'remarks',
            # Status tracking
            'is_processed', 'is_rejected', 'is_viewed', 'is_email_enabled',
            # Additional data
            'additional_data',
        ]

    def validate_email(self, value):
        """Validate email uniqueness within tenant"""
        if value:
            tenant = self.context['request'].tenant
            existing = ApplicantEnquiry.objects.filter(
                tenant=tenant,
                email=value
            ).exclude(id=self.instance.id)

            if existing.exists():
                raise serializers.ValidationError("An enquiry with this email already exists.")
        return value

    def update(self, instance, validated_data):
        """Update enquiry and track stage changes"""
        old_stage = instance.stage
        new_stage = validated_data.get('stage', instance.stage)

        enquiry = super().update(instance, validated_data)

        # Create stage log if stage changed
        if old_stage != new_stage and new_stage:
            EnquiryStageLog.objects.create(
                tenant=instance.tenant,
                enquiry=enquiry,
                stage=new_stage,
                changed_by=self.context['request'].user.employee_profile if hasattr(self.context['request'].user, 'employee_profile') else None
            )

        return enquiry


class EnquiryStatsSerializer(serializers.Serializer):
    """Serializer for enquiry statistics"""
    total_enquiries = serializers.IntegerField()
    processed_enquiries = serializers.IntegerField()
    pending_enquiries = serializers.IntegerField()
    rejected_enquiries = serializers.IntegerField()
    this_month_enquiries = serializers.IntegerField()
    stage_breakdown = serializers.DictField()
    course_breakdown = serializers.DictField()
    source_breakdown = serializers.DictField()


class EnquiryExportSerializer(serializers.Serializer):
    """Serializer for enquiry export requests"""
    format = serializers.ChoiceField(choices=['csv', 'excel', 'pdf'])
    stage = serializers.PrimaryKeyRelatedField(
        queryset=ApplicantEnquiryStage.objects.none(),
        required=False,
        allow_null=True
    )
    course = serializers.PrimaryKeyRelatedField(
        queryset=Course.objects.none(),
        required=False,
        allow_null=True
    )
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)

        if tenant:
            self.fields['stage'].queryset = ApplicantEnquiryStage.objects.filter(tenant=tenant)
            self.fields['course'].queryset = Course.objects.filter(tenant=tenant)