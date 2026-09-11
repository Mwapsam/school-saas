"""
Admission-related DRF serializers using AdmissionService
"""
from rest_framework import serializers
from datetime import date

from core.models import AdmissionApplication
from core.services.admission_service import AdmissionService
from .base import TenantAwareSerializer


class AdmissionApplicationSerializer(TenantAwareSerializer):
    """
    Admission Application serializer using AdmissionService
    """
    service_class = AdmissionService
    
    # Computed fields
    age = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    application_status = serializers.SerializerMethodField()
    # Course applied is referenced by UUID on input, name on output
    course_applied = serializers.UUIDField(write_only=True)
    course_name = serializers.CharField(source='course_applied.course_name', read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            'id', 'application_number', 'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'address',
            'guardian_name', 'guardian_phone', 'guardian_email',
            'course_applied', 'course_name', 'status', 'application_date',
            'remarks', 'age', 'full_name', 'application_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'application_number', 'application_date', 'status', 'remarks',
            'age', 'full_name', 'application_status', 'course_name',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
            'date_of_birth': {'required': True},
            'gender': {'required': True},
            'address': {'required': True},
            'guardian_name': {'required': True},
            'guardian_phone': {'required': True},
        }
    
    def get_age(self, obj):
        """Calculate applicant age"""
        if obj.date_of_birth:
            today = date.today()
            age = today.year - obj.date_of_birth.year
            if (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day):
                age -= 1
            return age
        return None
    
    def get_full_name(self, obj):
        """Get applicant full name"""
        parts = [obj.first_name]
        if obj.middle_name:
            parts.append(obj.middle_name)
        parts.append(obj.last_name)
        return ' '.join(parts)
    
    def get_application_status(self, obj):
        """Get application status"""
        return obj.status

    def validate_gender(self, value):
        """Validate gender choices"""
        valid_genders = ['male', 'female', 'other']
        if value.lower() not in valid_genders:
            raise serializers.ValidationError(f"Gender must be one of: {valid_genders}")
        return value.lower()
    
    def validate_date_of_birth(self, value):
        """Validate date of birth"""
        if value and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future")
        
        # Check minimum age (e.g., at least 3 years old)
        if value and (date.today().year - value.year) < 3:
            raise serializers.ValidationError("Applicant must be at least 3 years old")
        
        # Check maximum age (e.g., not older than 25 for school admission)
        if value and (date.today().year - value.year) > 25:
            raise serializers.ValidationError("Applicant age exceeds admission limit")
        
        return value
    
    def validate_guardian_email(self, value):
        """Validate guardian email format if provided"""
        if value and '@' not in value:
            raise serializers.ValidationError("Invalid email format")
        return value

    def validate_guardian_phone(self, value):
        """Validate guardian phone number"""
        if not value:
            raise serializers.ValidationError("Guardian phone number is required")
        
        clean_number = value.replace(' ', '').replace('-', '')
        if not clean_number.isdigit() or len(clean_number) < 10:
            raise serializers.ValidationError("Invalid guardian phone number format")
        
        return value
    
    def _service_create(self, service, validated_data):
        """Create admission application using AdmissionService"""
        return service.create_application(
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            date_of_birth=validated_data['date_of_birth'],
            gender=validated_data['gender'],
            course_id=str(validated_data['course_applied']),
            guardian_name=validated_data['guardian_name'],
            guardian_phone=validated_data['guardian_phone'],
            address=validated_data['address'],
            middle_name=validated_data.get('middle_name'),
            guardian_email=validated_data.get('guardian_email'),
        )

    def _service_update(self, service, instance, validated_data):
        """Update admission application using AdmissionService"""
        return service.update_application(str(instance.id), **validated_data)


class AdmissionApplicationListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for admission application lists
    """
    full_name = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    application_status = serializers.SerializerMethodField()
    
    class Meta:
        model = AdmissionApplication
        fields = [
            'id', 'application_number', 'full_name', 'gender', 'age',
            'guardian_name', 'guardian_phone', 'application_date',
            'application_status', 'status'
        ]
    
    def get_full_name(self, obj):
        """Get applicant full name"""
        parts = [obj.first_name]
        if obj.middle_name:
            parts.append(obj.middle_name)
        parts.append(obj.last_name)
        return ' '.join(parts)
    
    def get_age(self, obj):
        """Calculate applicant age"""
        if obj.date_of_birth:
            today = date.today()
            age = today.year - obj.date_of_birth.year
            if (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day):
                age -= 1
            return age
        return None
    
    def get_application_status(self, obj):
        """Get application status"""
        return obj.status


class AdmissionApprovalSerializer(serializers.Serializer):
    """
    Serializer for admission approval/rejection operations
    """
    application_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True)
    interview_date = serializers.DateTimeField(required=False, allow_null=True)
    
    def validate(self, attrs):
        """Validate approval data"""
        action = attrs.get('action')
        reason = attrs.get('reason')
        
        if action == 'reject' and not reason:
            raise serializers.ValidationError(
                "Reason is required when rejecting an application"
            )
        
        return attrs
    
    def save(self):
        """Process approval/rejection using AdmissionService"""
        tenant = self.context.get('tenant')
        if not tenant:
            raise serializers.ValidationError("Tenant context required")
        
        service = AdmissionService(tenant)
        application_id = str(self.validated_data['application_id'])
        action = self.validated_data['action']
        
        if action == 'approve':
            return service.approve_application(application_id)
        elif action == 'reject':
            reason = self.validated_data['reason']
            return service.reject_application(application_id, reason)


class AdmissionInterviewSerializer(serializers.Serializer):
    """
    Serializer for scheduling admission interviews
    """
    application_id = serializers.UUIDField()
    interview_date = serializers.DateTimeField()
    interviewer_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_interview_date(self, value):
        """Validate interview date"""
        from datetime import datetime
        
        if value and value < datetime.now():
            raise serializers.ValidationError(
                "Interview date cannot be in the past"
            )
        
        return value
    
    def save(self):
        """Schedule interview using AdmissionService"""
        tenant = self.context.get('tenant')
        service = AdmissionService(tenant)
        
        return service.schedule_interview(
            str(self.validated_data['application_id']),
            self.validated_data['interview_date'],
            self.validated_data.get('interviewer_notes')
        )


class AdmissionBulkApprovalSerializer(serializers.Serializer):
    """
    Serializer for bulk approval operations
    """
    application_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=50
    )
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate bulk approval data"""
        action = attrs.get('action')
        reason = attrs.get('reason')
        
        if action == 'reject' and not reason:
            raise serializers.ValidationError(
                "Reason is required when rejecting applications"
            )
        
        return attrs
    
    def save(self):
        """Process bulk approval/rejection using AdmissionService"""
        tenant = self.context.get('tenant')
        service = AdmissionService(tenant)
        
        application_ids = [str(id) for id in self.validated_data['application_ids']]
        action = self.validated_data['action']
        
        if action == 'approve':
            return service.bulk_approve_applications(application_ids)
        elif action == 'reject':
            reason = self.validated_data['reason']
            return service.bulk_reject_applications(application_ids, reason)


class AdmissionReportSerializer(serializers.Serializer):
    """
    Serializer for admission reports
    """
    report_type = serializers.ChoiceField(choices=[
        'applications_summary',
        'approval_statistics',
        'interview_schedule',
        'pending_applications'
    ])
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    status_filter = serializers.ChoiceField(
        choices=['all', 'pending', 'approved', 'rejected'],
        default='all'
    )
    
    def validate(self, attrs):
        """Validate report parameters"""
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                "date_from must be before or equal to date_to"
            )
        
        return attrs
    
    def generate_report(self):
        """Generate report using AdmissionService"""
        tenant = self.context.get('tenant')
        service = AdmissionService(tenant)
        
        report_type = self.validated_data['report_type']
        date_from = self.validated_data.get('date_from')
        date_to = self.validated_data.get('date_to')
        status_filter = self.validated_data.get('status_filter', 'all')
        
        return service.generate_admission_report(
            report_type=report_type,
            date_from=date_from,
            date_to=date_to,
            status_filter=status_filter
        )


class AdmissionSearchSerializer(serializers.Serializer):
    """
    Serializer for admission application search
    """
    query = serializers.CharField(required=True, min_length=1)
    status = serializers.ChoiceField(
        choices=['all', 'pending', 'approved', 'rejected'],
        default='all'
    )
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)
    
    def search(self):
        """Perform search using AdmissionService"""
        tenant = self.context.get('tenant')
        service = AdmissionService(tenant)
        
        return service.search_applications(
            query=self.validated_data['query'],
            status=self.validated_data.get('status', 'all'),
            date_from=self.validated_data.get('date_from'),
            date_to=self.validated_data.get('date_to'),
            limit=self.validated_data.get('limit', 20)
        )