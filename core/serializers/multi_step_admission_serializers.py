"""
Multi-step admission form DRF serializers (Django parity: 8 steps)
"""
from rest_framework import serializers
from datetime import date
from core.models import (
    ExtendedAdmissionApplication, AcademicYear, Course, Country, StudentCategory,
    AdmissionDocument, AdmissionTerms, AdditionalField, AdmissionAdditionalDetail
)
from core.services.extended_admission_service import ExtendedAdmissionService
from .base import TenantAwareSerializer


# ===== STEP 1: Terms and Conditions =====
class AdmissionStep1Serializer(TenantAwareSerializer):
    """Step 1: Terms and Conditions (agreement checkbox only)"""

    class Meta:
        model = ExtendedAdmissionApplication
        fields = ['id', 'terms_agreement', 'application_number', 'current_step', 'status']
        read_only_fields = ['id', 'application_number', 'current_step', 'status']

    def validate_terms_agreement(self, value):
        if not value:
            raise serializers.ValidationError("You must agree to the terms and conditions")
        return value

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class AdmissionTermsSerializer(serializers.ModelSerializer):
    """Lookup: Active admission terms and conditions"""
    class Meta:
        model = AdmissionTerms
        fields = ['id', 'title', 'terms_content', 'admission_fee', 'fee_currency', 'order']


# ===== STEP 2: Academic & Admission Details =====
class AdmissionStep2Serializer(TenantAwareSerializer):
    """Step 2: Academic year and course selection"""

    class Meta:
        model = ExtendedAdmissionApplication
        fields = ['id', 'academic_year', 'course_applied', 'application_number', 'current_step', 'status']
        read_only_fields = ['id', 'application_number', 'current_step', 'status']

    def validate_academic_year(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Selected academic year is not active")
        today = date.today()
        if value.admission_end_date and today > value.admission_end_date:
            raise serializers.ValidationError("Admission period for this academic year has ended")
        return value

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ===== STEP 3: Details of Child =====
class AdmissionStep3Serializer(TenantAwareSerializer):
    """Step 3: Student personal details, contact, and health information"""

    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id', 'first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender',
            'nationality', 'religion', 'birth_place', 'preferred_name', 'home_language',
            'email', 'student_photo', 'authorized_pickup_persons',
            'has_medical_problems', 'recent_hospitalization', 'has_allergies', 'medical_details',
            'application_number', 'current_step', 'status'
        ]
        read_only_fields = ['id', 'application_number', 'current_step', 'status']

    def validate_date_of_birth(self, value):
        if value and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future")
        if value and (date.today().year - value.year) < 3:
            raise serializers.ValidationError("Student must be at least 3 years old")
        if value and (date.today().year - value.year) > 25:
            raise serializers.ValidationError("Student age exceeds admission limit")
        return value

    def validate_gender(self, value):
        valid_genders = ['male', 'female', 'other']
        if value and value.lower() not in valid_genders:
            raise serializers.ValidationError(f"Gender must be one of: {valid_genders}")
        return value.lower() if value else value

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ===== STEP 4: Guardian 1 =====
class AdmissionStep4Serializer(TenantAwareSerializer):
    """Step 4: Primary guardian personal and professional details"""
    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id',
            'guardian1_first_name', 'guardian1_last_name', 'guardian1_relation',
            'guardian1_mobile', 'guardian1_email',
            'guardian1_occupation', 'guardian1_office_phone1', 'guardian1_office_address_line1', 'guardian1_city',
            'guardian1_house_plot_no', 'guardian1_road_name', 'guardian1_area_location', 'guardian1_flat_block_name',
            'application_number', 'current_step', 'status'
        ]
        read_only_fields = ['id', 'application_number', 'current_step', 'status']

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ===== STEP 5: Guardian 2 & Emergency Contact =====
class AdmissionStep5Serializer(TenantAwareSerializer):
    """Step 5: Secondary guardian (optional) and alternative emergency contact"""
    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id',
            'guardian2_first_name', 'guardian2_last_name', 'guardian2_relation',
            'guardian2_mobile', 'guardian2_email',
            'guardian2_occupation', 'guardian2_office_phone1', 'guardian2_office_address_line1', 'guardian2_city',
            'guardian2_house_plot_no', 'guardian2_road_name', 'guardian2_area_location', 'guardian2_flat_block_name',
            'emergency_contact_name', 'emergency_contact_relation', 'emergency_contact_mobile', 'emergency_contact_address',
            'application_number', 'current_step', 'status'
        ]
        read_only_fields = ['id', 'application_number', 'current_step', 'status']

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ===== STEP 6: Student Address & Additional Information =====
class AdditionalFieldValueSerializer(serializers.Serializer):
    """Dynamic additional field value (for Step 6)"""
    field_id = serializers.CharField()
    value = serializers.CharField(allow_blank=True)


class AdmissionStep6Serializer(TenantAwareSerializer):
    """Step 6: Student address, previous school, additional school-specific information, and dynamic additional fields"""
    additional_field_values = AdditionalFieldValueSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id',
            'address_line1', 'address_line2', 'city', 'country', 'phone', 'mobile',
            'previous_school_name', 'previous_school_address', 'previous_school_phone', 'previous_school_email',
            'expected_start_date', 'religious_observances', 'background_information',
            'additional_field_values',
            'application_number', 'current_step', 'status'
        ]
        read_only_fields = ['id', 'application_number', 'current_step', 'status']

    def create(self, validated_data):
        additional_values = validated_data.pop('additional_field_values', [])
        instance = super().create(validated_data)
        self._save_additional_fields(instance, additional_values)
        return instance

    def update(self, instance, validated_data):
        additional_values = validated_data.pop('additional_field_values', None)
        instance = super().update(instance, validated_data)
        if additional_values is not None:
            self._save_additional_fields(instance, additional_values)
        return instance

    def _save_additional_fields(self, instance, additional_values):
        """Save additional field values"""
        if additional_values:
            for item in additional_values:
                try:
                    field = AdditionalField.objects.get(id=item['field_id'], tenant=instance.tenant)
                    AdmissionAdditionalDetail.objects.update_or_create(
                        application=instance,
                        field=field,
                        defaults={'value': item.get('value', '')}
                    )
                except AdditionalField.DoesNotExist:
                    pass


class AdditionalFieldLookupSerializer(serializers.ModelSerializer):
    """Lookup: Dynamic admission fields (configuration-driven)"""
    options = serializers.SerializerMethodField()

    class Meta:
        model = AdditionalField
        fields = ['id', 'name', 'input_type', 'is_mandatory', 'options']

    def get_options(self, obj):
        if obj.option_list:
            return obj.option_list if isinstance(obj.option_list, list) else []
        return []


# ===== STEP 8: Declaration & Submission =====
class AdmissionStep8Serializer(TenantAwareSerializer):
    """Step 8: Final declaration, signature, and submission"""
    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id', 'declaration_agreement', 'declaration_date', 'declaration_signature_name',
            'fee_acknowledgment', 'application_number', 'current_step', 'status'
        ]
        read_only_fields = ['id', 'application_number', 'current_step', 'status']

    def validate_declaration_agreement(self, value):
        if not value:
            raise serializers.ValidationError("You must agree to the declaration")
        return value

    def validate_declaration_signature_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Please provide your full name as signature")
        return value

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ===== PROGRESS TRACKING =====
class AdmissionProgressSerializer(serializers.ModelSerializer):
    """Get completion status for all steps"""
    step1_complete = serializers.SerializerMethodField()
    step2_complete = serializers.SerializerMethodField()
    step3_complete = serializers.SerializerMethodField()
    step4_complete = serializers.SerializerMethodField()
    step5_complete = serializers.SerializerMethodField()
    step6_complete = serializers.SerializerMethodField()
    step7_complete = serializers.SerializerMethodField()

    class Meta:
        model = ExtendedAdmissionApplication
        fields = [
            'id', 'current_step', 'status',
            'step1_complete', 'step2_complete', 'step3_complete', 'step4_complete',
            'step5_complete', 'step6_complete', 'step7_complete'
        ]

    def get_step1_complete(self, obj): return obj.is_step1_complete
    def get_step2_complete(self, obj): return obj.is_step2_complete
    def get_step3_complete(self, obj): return obj.is_step3_complete
    def get_step4_complete(self, obj): return obj.is_step4_complete
    def get_step5_complete(self, obj): return obj.is_step5_complete
    def get_step6_complete(self, obj): return obj.is_step6_complete
    def get_step7_complete(self, obj): return obj.is_step7_complete


# ===== EXTENDED DETAIL =====
class ExtendedAdmissionApplicationSerializer(serializers.ModelSerializer):
    """Full application detail with nested relationships"""
    class Meta:
        model = ExtendedAdmissionApplication
        fields = '__all__'


# ===== LOOKUPS =====
class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ['id', 'name', 'start_date', 'end_date', 'is_active']


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'course_name', 'code', 'section_name']


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code']


class StudentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentCategory
        fields = ['id', 'name']


class AdmissionDocumentSerializer(TenantAwareSerializer):
    """Document upload serializer"""
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)

    class Meta:
        model = AdmissionDocument
        fields = [
            'id', 'document_type', 'document_type_display', 'file', 'original_filename',
            'file_size', 'uploaded_at', 'is_verified'
        ]
        read_only_fields = ['id', 'uploaded_at', 'is_verified', 'document_type_display']

    def validate_file(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 5MB")
        return value


# ===== APPLICATION DETAIL =====
class AdmissionApplicationDetailSerializer(serializers.ModelSerializer):
    """
    Full application detail for single-record API response.
    Includes nested documents, academic year, course, and all application fields.
    """
    documents = AdmissionDocumentSerializer(many=True, read_only=True)
    academic_year_detail = AcademicYearSerializer(source='academic_year', read_only=True)
    course_detail = CourseSerializer(source='course_applied', read_only=True)
    student_category_detail = StudentCategorySerializer(source='student_category', read_only=True)
    country_detail = CountrySerializer(source='country', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True, allow_null=True)
    admitted_student_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ExtendedAdmissionApplication
        fields = '__all__'

    def get_admitted_student_details(self, obj):
        """Return admitted student record if admission completed"""
        if obj.admitted_student:
            from core.serializers.student_serializers import StudentDetailSerializer
            return StudentDetailSerializer(obj.admitted_student, read_only=True).data
        return None


# ===== SUPPORT SERIALIZERS =====
class BulkAdmissionStatusSerializer(serializers.Serializer):
    """Bulk status updates (admin only)"""
    application_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1
    )
    status = serializers.ChoiceField(choices=['under_review', 'approved', 'rejected', 'waitlisted'])
    reason = serializers.CharField(required=False, allow_blank=True)


class AdmissionStepAdvanceSerializer(serializers.Serializer):
    """Serializer for advancing to next step"""
    step = serializers.IntegerField(min_value=1, max_value=8)


class AdmissionSubmissionSerializer(serializers.Serializer):
    """Serializer for final submission"""
    confirm_submission = serializers.BooleanField()

    def validate_confirm_submission(self, value):
        if not value:
            raise serializers.ValidationError("You must confirm the submission")
        return value
