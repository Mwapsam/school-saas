"""
Multi-step admission form DRF serializers
"""
from rest_framework import serializers
from datetime import date, datetime
from django.core.exceptions import ValidationError

from core.models import ExtendedAdmissionApplication, AcademicYear, Course, Country, StudentCategory, AdmissionDocument
from .base import TenantAwareSerializer


class AdmissionStep1Serializer(TenantAwareSerializer):
    """
    Step 1: Academic Year Selection, Class Selection, Terms and Conditions
    """

    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id', 'academic_year', 'course_applied', 'terms_agreement', 'preferred_start_date',
            'application_number', 'current_step', 'status'
        ]
        read_only_fields = ['id', 'application_number', 'current_step', 'status']
    
    def validate_terms_agreement(self, value):
        """Terms and conditions must be agreed to"""
        if not value:
            raise serializers.ValidationError("You must agree to the terms and conditions")
        return value
    
    def validate_academic_year(self, value):
        """Validate academic year is active and accepting admissions"""
        if not value.is_active:
            raise serializers.ValidationError("Selected academic year is not active")
        
        today = date.today()
        if value.admission_end_date and today > value.admission_end_date:
            raise serializers.ValidationError("Admission period for this academic year has ended")
        
        return value


class AdmissionStep2Serializer(TenantAwareSerializer):
    """
    Step 2: Student Personal Details
    """
    
    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id', 'first_name', 'middle_name', 'last_name', 'date_of_birth',
            'gender', 'nationality', 'student_photo', 'student_category',
            'religion', 'birth_place', 'mother_tongue', 'preferred_name',
            'home_language', 'authorized_pickup_persons', 'current_step', 'status'
        ]
        read_only_fields = ['id', 'current_step', 'status']
    
    def validate_date_of_birth(self, value):
        """Validate date of birth"""
        if value and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future")
        
        if value and (date.today().year - value.year) < 3:
            raise serializers.ValidationError("Student must be at least 3 years old")
        
        if value and (date.today().year - value.year) > 25:
            raise serializers.ValidationError("Student age exceeds admission limit")
        
        return value
    
    def validate_gender(self, value):
        """Validate gender choices"""
        valid_genders = ['male', 'female', 'other']
        if value and value.lower() not in valid_genders:
            raise serializers.ValidationError(f"Gender must be one of: {valid_genders}")
        return value.lower() if value else value


class AdmissionStep3Serializer(TenantAwareSerializer):
    """
    Step 3: Student Communication Details
    """

    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id', 'address', 'address_line1', 'address_line2', 'city', 'country',
            'phone', 'mobile', 'email', 'current_step', 'status'
        ]
        read_only_fields = ['id', 'current_step', 'status']
    
    def validate_email(self, value):
        """Validate email format"""
        if value and '@' not in value:
            raise serializers.ValidationError("Invalid email format")
        return value
    
    def validate_phone(self, value):
        """Validate phone number format"""
        if value:
            clean_number = value.replace(' ', '').replace('-', '').replace('+', '')
            if not clean_number.isdigit() or len(clean_number) < 9:
                raise serializers.ValidationError("Invalid phone number format")
        return value
    
    def validate_mobile(self, value):
        """Validate mobile number format"""
        if value:
            clean_number = value.replace(' ', '').replace('-', '').replace('+', '')
            if not clean_number.isdigit() or len(clean_number) < 9:
                raise serializers.ValidationError("Invalid mobile number format")
        return value


class AdmissionStep4Serializer(TenantAwareSerializer):
    """
    Step 4: Guardian Personal Details - Guardian 1 & Guardian 2
    """
    
    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id', 'guardian1_first_name', 'guardian1_last_name', 'guardian1_relation',
            'guardian1_occupation', 'guardian1_office_address_line1', 'guardian1_office_city',
            'guardian1_office_phone1', 'guardian1_mobile', 'guardian1_email',
            'guardian1_house_plot_no', 'guardian1_road_name', 'guardian1_area_location',
            'guardian1_flat_block_name',
            'guardian2_first_name', 'guardian2_last_name', 'guardian2_relation',
            'guardian2_occupation', 'guardian2_office_address_line1', 'guardian2_office_city',
            'guardian2_office_phone1', 'guardian2_mobile', 'guardian2_email',
            'guardian2_house_plot_no', 'guardian2_road_name', 'guardian2_area_location',
            'guardian2_flat_block_name',
            'emergency_contact_name', 'emergency_contact_relation',
            'emergency_contact_mobile', 'emergency_contact_address',
            'current_step', 'status'
        ]
        read_only_fields = ['id', 'current_step', 'status']
    
    def validate_guardian1_email(self, value):
        """Validate guardian 1 email format"""
        if value and '@' not in value:
            raise serializers.ValidationError("Invalid email format")
        return value
    
    def validate_guardian2_email(self, value):
        """Validate guardian 2 email format"""
        if value and '@' not in value:
            raise serializers.ValidationError("Invalid email format")
        return value
    
    def validate_guardian1_mobile(self, value):
        """Validate guardian 1 mobile number"""
        if value:
            clean_number = value.replace(' ', '').replace('-', '').replace('+', '')
            if not clean_number.isdigit() or len(clean_number) < 9:
                raise serializers.ValidationError("Invalid mobile number format")
        return value
    
    def validate_guardian2_mobile(self, value):
        """Validate guardian 2 mobile number"""
        if value:
            clean_number = value.replace(' ', '').replace('-', '').replace('+', '')
            if not clean_number.isdigit() or len(clean_number) < 9:
                raise serializers.ValidationError("Invalid mobile number format")
        return value
    
    def validate_guardian1_office_phone1(self, value):
        """Validate guardian 1 office phone"""
        if value:
            clean_number = value.replace(' ', '').replace('-', '').replace('+', '')
            if not clean_number.isdigit() or len(clean_number) < 9:
                raise serializers.ValidationError("Invalid phone number format")
        return value
    
    def validate_guardian2_office_phone1(self, value):
        """Validate guardian 2 office phone"""
        if value:
            clean_number = value.replace(' ', '').replace('-', '').replace('+', '')
            if not clean_number.isdigit() or len(clean_number) < 9:
                raise serializers.ValidationError("Invalid phone number format")
        return value


class AdmissionStep5Serializer(TenantAwareSerializer):
    """
    Step 5: Previous School, Health Information, Background Information, Documents, Declaration
    """

    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id', 'previous_school_name', 'previous_school_address', 'previous_school_phone',
            'previous_school_email', 'expected_start_date', 'has_medical_problems',
            'recent_hospitalization', 'has_allergies', 'medical_details',
            'religious_observances', 'background_information', 'declaration_agreement',
            'declaration_date', 'declaration_signature_name', 'fee_acknowledgment', 'current_step', 'status'
        ]
        read_only_fields = ['id', 'current_step', 'status']
    
    def validate_previous_school_email(self, value):
        """Validate previous school email format"""
        if value and '@' not in value:
            raise serializers.ValidationError("Invalid email format")
        return value
    
    def validate_previous_school_phone(self, value):
        """Validate previous school phone number"""
        if value:
            clean_number = value.replace(' ', '').replace('-', '').replace('+', '')
            if not clean_number.isdigit() or len(clean_number) < 9:
                raise serializers.ValidationError("Invalid phone number format")
        return value
    
    def validate_expected_start_date(self, value):
        """Validate expected start date"""
        if value and value < date.today():
            raise serializers.ValidationError("Expected start date cannot be in the past")
        return value
    
    def validate_declaration_agreement(self, value):
        """Declaration must be agreed to"""
        if not value:
            raise serializers.ValidationError("You must agree to the declaration")
        return value
    
    def validate(self, attrs):
        """Cross-field validation"""
        has_medical = attrs.get('has_medical_problems')
        has_hospital = attrs.get('recent_hospitalization')
        has_allergies = attrs.get('has_allergies')
        medical_details = attrs.get('medical_details', '').strip()
        
        if (has_medical or has_hospital or has_allergies) and not medical_details:
            raise serializers.ValidationError(
                "Medical details are required when any health questions are answered 'Yes'"
            )
        
        return attrs


class ExtendedAdmissionApplicationSerializer(TenantAwareSerializer):
    """
    Complete Extended Admission Application serializer
    """
    full_name = serializers.ReadOnlyField()
    is_step1_complete = serializers.ReadOnlyField()
    is_step2_complete = serializers.ReadOnlyField()
    is_step3_complete = serializers.ReadOnlyField()
    is_step4_complete = serializers.ReadOnlyField()
    is_step5_complete = serializers.ReadOnlyField()
    is_step6_complete = serializers.ReadOnlyField()
    is_step7_complete = serializers.ReadOnlyField()
    is_complete = serializers.ReadOnlyField()
    can_submit = serializers.ReadOnlyField()
    next_step = serializers.SerializerMethodField()

    class Meta:
        model = ExtendedAdmissionApplication
        fields = '__all__'
        read_only_fields = [
            'id', 'application_number', 'application_date', 'reviewed_by', 'reviewed_at',
            'full_name', 'is_step1_complete', 'is_step2_complete', 'is_step3_complete',
            'is_step4_complete', 'is_step5_complete', 'is_step6_complete', 'is_step7_complete',
            'is_complete', 'can_submit', 'next_step'
        ]

    def get_next_step(self, obj):
        """Get next incomplete step"""
        return obj.get_next_step()


class AdmissionDocumentSerializer(TenantAwareSerializer):
    """
    Document upload serializer
    """
    file_size_mb = serializers.ReadOnlyField()
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    
    class Meta:
        model = AdmissionDocument
        fields = [
            'id', 'document_type', 'document_type_display', 'file', 'original_filename',
            'file_size', 'file_size_mb', 'uploaded_at', 'is_verified', 'is_required', 
            'verification_notes'
        ]
        read_only_fields = [
            'id', 'file_size', 'file_size_mb', 'uploaded_at', 'is_verified',
            'verification_notes', 'document_type_display'
        ]
    
    def validate_file(self, value):
        """Validate file upload"""
        if value:
            # Check file size (max 5MB)
            if value.size > 5 * 1024 * 1024:
                raise serializers.ValidationError("File size cannot exceed 5MB")
            
            # Check file extension
            allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png']
            file_extension = value.name.split('.')[-1].lower()
            if file_extension not in allowed_extensions:
                raise serializers.ValidationError(
                    f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
                )
        
        return value
    
    def create(self, validated_data):
        """Create document with file metadata"""
        validated_data['original_filename'] = validated_data['file'].name
        validated_data['file_size'] = validated_data['file'].size
        return super().create(validated_data)


class AdmissionProgressSerializer(serializers.Serializer):
    """
    Serializer for tracking admission progress
    """
    current_step = serializers.IntegerField(read_only=True)
    status = serializers.CharField(read_only=True)
    step1_complete = serializers.BooleanField(read_only=True)
    step2_complete = serializers.BooleanField(read_only=True)
    step3_complete = serializers.BooleanField(read_only=True)
    step4_complete = serializers.BooleanField(read_only=True)
    step5_complete = serializers.BooleanField(read_only=True)
    step6_complete = serializers.BooleanField(read_only=True)
    step7_complete = serializers.BooleanField(read_only=True)
    is_complete = serializers.BooleanField(read_only=True)
    can_submit = serializers.BooleanField(read_only=True)
    next_step = serializers.IntegerField(read_only=True, allow_null=True)
    documents_uploaded = serializers.IntegerField(read_only=True)
    required_documents_uploaded = serializers.IntegerField(read_only=True)


class AcademicYearSerializer(serializers.ModelSerializer):
    """
    Simple Academic Year serializer for dropdown
    """
    
    class Meta:
        model = AcademicYear
        fields = ['id', 'name', 'start_date', 'end_date', 'is_active', 'admission_start_date', 'admission_end_date']


class CourseSerializer(serializers.ModelSerializer):
    """
    Simple Course serializer for dropdown
    """
    
    class Meta:
        model = Course
        fields = ['id', 'course_name', 'code', 'section_name']


class CountrySerializer(serializers.ModelSerializer):
    """
    Simple Country serializer for dropdown
    """
    
    class Meta:
        model = Country
        fields = ['id', 'name', 'code']


class StudentCategorySerializer(serializers.ModelSerializer):
    """
    Simple Student Category serializer for dropdown
    """
    
    class Meta:
        model = StudentCategory
        fields = ['id', 'name']


class AdmissionStepAdvanceSerializer(serializers.Serializer):
    """
    Serializer for advancing to next step
    """
    step = serializers.IntegerField(min_value=1, max_value=5)
    
    def validate_step(self, value):
        """Validate step can be advanced to"""
        application = self.context.get('application')
        if not application:
            raise serializers.ValidationError("Application context required")
        
        next_available_step = application.get_next_step()
        if next_available_step and value != next_available_step:
            raise serializers.ValidationError(
                f"Cannot advance to step {value}. Complete step {next_available_step} first."
            )
        
        return value


class AdmissionSubmissionSerializer(serializers.Serializer):
    """
    Serializer for final submission
    """
    confirm_submission = serializers.BooleanField()
    
    def validate_confirm_submission(self, value):
        """Confirm submission checkbox must be checked"""
        if not value:
            raise serializers.ValidationError("You must confirm the submission")
        return value
    
    def validate(self, attrs):
        """Validate application is ready for submission"""
        application = self.context.get('application')
        if not application:
            raise serializers.ValidationError("Application context required")
        
        if not application.can_submit():
            raise serializers.ValidationError("Application is not complete or not ready for submission")
        
        return attrs


class BulkAdmissionStatusSerializer(serializers.Serializer):
    """
    Serializer for bulk status updates (admin only)
    """
    application_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=50
    )
    status = serializers.ChoiceField(choices=[
        'under_review', 'approved', 'rejected', 'waitlisted'
    ])
    reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate bulk status update"""
        status = attrs.get('status')
        reason = attrs.get('reason', '').strip()
        
        if status == 'rejected' and not reason:
            raise serializers.ValidationError("Reason is required when rejecting applications")
        
        return attrs