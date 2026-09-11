"""
Student-related DRF serializers using StudentService
"""
from rest_framework import serializers
from datetime import date

from django.db import models
from core.models import Student, Guardian, Country, StudentCategory
from core.services.student_service import StudentService
from .base import TenantAwareSerializer, ReadOnlyServiceSerializer


class StudentSerializer(TenantAwareSerializer):
    """
    Main Student serializer that uses StudentService for business logic
    """
    service_class = StudentService
    
    # Computed fields
    age = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    
    # Write-only fields for creation
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Student
        fields = [
            'id', 'admission_no', 'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'admission_date', 'blood_group',
            'nationality', 'language', 'religion', 'student_category',
            'address_line1', 'address_line2', 'city', 'state', 'pin_code',
            'country', 'phone1', 'phone2', 'email', 'is_sms_enabled',
            'is_active', 'status_description', 'has_paid_fees',
            'age', 'full_name', 'password', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'age', 'full_name', 'created_at', 'updated_at']
        extra_kwargs = {
            'admission_no': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
            'date_of_birth': {'required': True},
            'gender': {'required': True},
        }
    
    def get_age(self, obj):
        """Calculate student age from date_of_birth.

        Computed directly off the already-loaded instance to avoid a per-row
        service call that re-fetches the student from the DB.
        """
        if obj.date_of_birth:
            today = date.today()
            age = today.year - obj.date_of_birth.year
            if (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day):
                age -= 1
            return age
        return None
    
    def get_full_name(self, obj):
        """Get student full name"""
        parts = [obj.first_name]
        if obj.middle_name:
            parts.append(obj.middle_name)
        parts.append(obj.last_name)
        return ' '.join(parts)
    
    def validate_admission_no(self, value):
        """Validate admission number format"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Admission number cannot be empty")
        
        # Custom format validation (adjust as needed)
        if len(value) < 3:
            raise serializers.ValidationError("Admission number must be at least 3 characters")
        
        return value.strip()
    
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
        
        # Check minimum age (e.g., not older than 100 years)
        if value and (date.today().year - value.year) > 100:
            raise serializers.ValidationError("Invalid date of birth - too old")
        
        return value
    
    def validate_email(self, value):
        """Validate email format if provided"""
        if value and '@' not in value:
            raise serializers.ValidationError("Invalid email format")
        return value
    
    def _service_create(self, service, validated_data):
        """Use StudentService to create student"""
        # Extract password if provided (for creating user account)
        password = validated_data.pop('password', None)
        
        # Use service method that includes business logic
        student = service.create_student(**validated_data)
        
        # Handle user account creation if password provided
        if password:
            # This would integrate with UserService to create login account
            # user_service = UserService(service.tenant)
            # user_service.create_student_user(student, password)
            pass
        
        return student
    
    def _service_update(self, service, instance, validated_data):
        """Use StudentService to update student"""
        return service.update_student(str(instance.id), **validated_data)


class StudentListSerializer(ReadOnlyServiceSerializer):
    """
    Optimized serializer for student lists - only essential fields
    """
    service_class = StudentService
    
    age = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    batch_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = [
            'id', 'admission_no', 'full_name', 'gender', 'age',
            'batch_name', 'is_active', 'has_paid_fees'
        ]
    
    def get_age(self, obj):
        """Get age - optimized calculation"""
        if obj.date_of_birth:
            today = date.today()
            age = today.year - obj.date_of_birth.year
            if (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day):
                age -= 1
            return age
        return None
    
    def get_full_name(self, obj):
        """Get full name"""
        parts = [obj.first_name]
        if obj.middle_name:
            parts.append(obj.middle_name)
        parts.append(obj.last_name)
        return ' '.join(parts)
    
    def get_batch_name(self, obj):
        """Get current batch name"""
        # This would be optimized with select_related in the view
        try:
            active_enrollment = obj.student_batches.filter(is_active=True).first()
            return active_enrollment.batch.name if active_enrollment else None
        except AttributeError:
            return None


class StudentDetailSerializer(TenantAwareSerializer):
    """
    Detailed serializer for individual student view - includes relationships
    """
    service_class = StudentService
    
    # Related fields
    guardians = serializers.SerializerMethodField()
    batches = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    
    # Nested objects (read-only)
    country_name = serializers.CharField(source='country.name', read_only=True)
    nationality_name = serializers.CharField(source='nationality.name', read_only=True)
    category_name = serializers.CharField(source='student_category.name', read_only=True)
    
    class Meta:
        model = Student
        fields = '__all__'
        read_only_fields = [
            'id', 'age', 'full_name', 'guardians', 'batches',
            'country_name', 'nationality_name', 'category_name',
            'created_at', 'updated_at'
        ]
    
    def get_age(self, obj):
        """Get calculated age"""
        try:
            service = self.get_service()
            return service.calculate_age(str(obj.id))
        except Exception:
            return None
    
    def get_full_name(self, obj):
        """Get full name"""
        parts = [obj.first_name]
        if obj.middle_name:
            parts.append(obj.middle_name)
        parts.append(obj.last_name)
        return ' '.join(parts)
    
    def get_guardians(self, obj):
        """Get student guardians"""
        try:
            relations = obj.guardian_relations.select_related('guardian').all()
            return [
                {
                    'id': relation.guardian.id,
                    'name': f"{relation.guardian.first_name} {relation.guardian.last_name}",
                    'relationship': relation.relationship,
                    'phone': relation.guardian.phone1,
                    'email': relation.guardian.email,
                    'is_immediate_contact': relation.is_immediate_contact
                }
                for relation in relations
            ]
        except AttributeError:
            return []
    
    def get_batches(self, obj):
        """Get student batch history"""
        try:
            enrollments = obj.student_batches.select_related('batch').order_by('-created_at')
            return [
                {
                    'id': enrollment.batch.id,
                    'name': enrollment.batch.name,
                    'roll_number': enrollment.roll_number,
                    'is_active': enrollment.is_active,
                    'enrollment_date': enrollment.created_at
                }
                for enrollment in enrollments
            ]
        except AttributeError:
            return []


class GuardianSerializer(TenantAwareSerializer):
    """
    Guardian serializer for student relationships
    """
    
    class Meta:
        model = Guardian
        fields = [
            'id', 'first_name', 'last_name', 'gender', 'date_of_birth',
            'phone1', 'phone2', 'email', 'address_line1', 'address_line2',
            'city', 'state', 'country', 'pin_code', 'income',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StudentBulkCreateSerializer(serializers.Serializer):
    """
    Serializer for bulk student creation
    """
    students = StudentSerializer(many=True)
    batch_id = serializers.UUIDField(required=False, allow_null=True)
    
    def create(self, validated_data):
        """Bulk create students using service"""
        try:
            tenant = self.context.get('tenant')
            service = StudentService(tenant)
            
            students_data = validated_data['students']
            batch_id = validated_data.get('batch_id')
            
            return service.bulk_create_students(students_data, str(batch_id) if batch_id else None)
        
        except Exception as e:
            raise serializers.ValidationError(f"Bulk creation failed: {str(e)}")


class StudentSearchSerializer(serializers.Serializer):
    """
    Serializer for student search parameters
    """
    query = serializers.CharField(required=True, min_length=1)
    active_only = serializers.BooleanField(default=True)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)
    batch_id = serializers.UUIDField(required=False, allow_null=True)
    
    def search(self):
        """Perform search using StudentService"""
        tenant = self.context.get('tenant')
        if not tenant:
            raise serializers.ValidationError("Tenant context required")
        
        service = StudentService(tenant)
        validated_data = self.validated_data
        
        if validated_data.get('batch_id'):
            # Search within specific batch
            students = service.get_students_by_batch(
                str(validated_data['batch_id']),
                validated_data['active_only']
            )
            # Filter by query
            query = validated_data['query']
            students = students.filter(
                models.Q(first_name__icontains=query) |
                models.Q(last_name__icontains=query) |
                models.Q(admission_no__icontains=query)
            )
        else:
            # General search
            students = service.search_students(
                validated_data['query'],
                validated_data['active_only'],
                validated_data['limit']
            )
        
        return students