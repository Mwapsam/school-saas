"""
Academic-related DRF serializers using AcademicService
"""
from rest_framework import serializers
from datetime import datetime

from core.models import Course, Batch, Subject, BatchStudent, Timetable, Attendance, AcademicYear, Weekday, ClassTiming
from core.services.academic_service import AcademicService
from .base import TenantAwareSerializer, ReadOnlyServiceSerializer


class CourseSerializer(TenantAwareSerializer):
    """
    Course serializer using AcademicService
    """
    service_class = AcademicService
    
    # Computed fields
    batch_count = serializers.SerializerMethodField()
    active_batch_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'course_name', 'code', 'section_name', 'grading_type',
            'max_hours_day', 'max_hours_week', 'is_deleted', 
            'batch_count', 'active_batch_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'batch_count', 'active_batch_count', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'course_name': {'required': True},
            'code': {'required': True},
        }
    
    def get_batch_count(self, obj):
        """Get total batch count for this course (prefers queryset annotation)."""
        annotated = getattr(obj, 'batch_count_anno', None)
        if annotated is not None:
            return annotated
        try:
            return obj.batches.count()
        except AttributeError:
            return 0

    def get_active_batch_count(self, obj):
        """Get active batch count for this course (prefers queryset annotation)."""
        annotated = getattr(obj, 'active_batch_count_anno', None)
        if annotated is not None:
            return annotated
        try:
            return obj.batches.filter(is_active=True).count()
        except AttributeError:
            return 0
    
    def validate_code(self, value):
        """Validate course code uniqueness"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Course code cannot be empty")
        
        value = value.strip().upper()
        
        # Check uniqueness within tenant
        tenant = self.context.get('tenant')
        if tenant:
            existing = Course.objects.filter(
                code=value, 
                tenant=tenant
            ).exclude(id=self.instance.id if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError("Course code already exists")
        
        return value
    
    def _service_create(self, service, validated_data):
        """Create course using AcademicService"""
        return service.create_course(
            course_name=validated_data['course_name'],
            code=validated_data['code'],
            section_name=validated_data.get('section_name'),
            grading_type=validated_data.get('grading_type'),
            max_hours_day=validated_data.get('max_hours_day'),
            max_hours_week=validated_data.get('max_hours_week')
        )
    
    def _service_update(self, service, instance, validated_data):
        """Update course using AcademicService"""
        return service.update_course(str(instance.id), **validated_data)


class BatchSerializer(TenantAwareSerializer):
    """
    Batch serializer using AcademicService
    """
    service_class = AcademicService
    
    # Related fields
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    
    # Computed fields
    student_count = serializers.SerializerMethodField()
    active_student_count = serializers.SerializerMethodField()
    subject_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = [
            'id', 'name', 'course', 'course_name', 'course_code',
            'start_date', 'end_date', 'is_active', 'grading_type',
            'student_count', 'active_student_count', 'subject_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'course_name', 'course_code', 'student_count',
            'active_student_count', 'subject_count', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'name': {'required': True},
            'course': {'required': True},
            'start_date': {'required': True},
            'end_date': {'required': True},
        }
    
    def get_student_count(self, obj):
        """Get total student count in batch (prefers queryset annotation)."""
        annotated = getattr(obj, 'student_count_anno', None)
        if annotated is not None:
            return annotated
        try:
            return obj.batch_students.count()
        except AttributeError:
            return 0

    def get_active_student_count(self, obj):
        """Get active student count in batch (prefers queryset annotation)."""
        annotated = getattr(obj, 'active_student_count_anno', None)
        if annotated is not None:
            return annotated
        try:
            return obj.batch_students.filter(is_active=True).count()
        except AttributeError:
            return 0

    def get_subject_count(self, obj):
        """Get subject count for batch (prefers queryset annotation)."""
        annotated = getattr(obj, 'subject_count_anno', None)
        if annotated is not None:
            return annotated
        try:
            return obj.subjects.count()
        except AttributeError:
            return 0
    
    def validate(self, attrs):
        """Validate batch dates"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError("End date must be after start date")
        
        return super().validate(attrs)
    
    def _service_create(self, service, validated_data):
        """Create batch using AcademicService"""
        return service.create_batch(
            name=validated_data['name'],
            course_id=str(validated_data['course'].id),
            start_date=validated_data['start_date'],
            end_date=validated_data['end_date'],
            grading_type=validated_data.get('grading_type')
        )
    
    def _service_update(self, service, instance, validated_data):
        """Update batch using AcademicService"""
        return service.update_batch(str(instance.id), **validated_data)


class SubjectSerializer(TenantAwareSerializer):
    """
    Subject serializer using AcademicService
    """
    service_class = AcademicService
    
    # Related fields
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    
    class Meta:
        model = Subject
        fields = [
            'id', 'name', 'code', 'batch', 'batch_name', 'no_exams',
            'max_weekly_classes', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'batch_name', 'created_at', 'updated_at']
        extra_kwargs = {
            'name': {'required': True},
            'code': {'required': True},
            'batch': {'required': True},
        }
    
    def validate_code(self, value):
        """Validate subject code"""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Subject code cannot be empty")
        return value.strip().upper()
    
    def _service_create(self, service, validated_data):
        """Create subject using AcademicService"""
        return service.create_subject(
            name=validated_data['name'],
            code=validated_data['code'],
            batch_id=str(validated_data['batch'].id),
            no_exams=validated_data.get('no_exams', False),
            max_weekly_classes=validated_data.get('max_weekly_classes')
        )
    
    def _service_update(self, service, instance, validated_data):
        """Update subject using AcademicService"""
        return service.update_subject(str(instance.id), **validated_data)


class BatchStudentSerializer(TenantAwareSerializer):
    """
    Serializer for batch-student enrollments
    """
    service_class = AcademicService
    
    # Related fields
    student_name = serializers.CharField(source='student.first_name', read_only=True)
    student_admission_no = serializers.CharField(source='student.admission_no', read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    
    class Meta:
        model = BatchStudent
        fields = [
            'id', 'student', 'batch', 'student_name', 'student_admission_no',
            'batch_name', 'roll_number', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'student_name', 'student_admission_no', 'batch_name',
            'created_at', 'updated_at'
        ]
    
    def validate(self, attrs):
        """Validate enrollment data"""
        student = attrs.get('student')
        batch = attrs.get('batch')
        
        if student and batch:
            # Check for existing active enrollment
            tenant = self.context.get('tenant')
            existing = BatchStudent.objects.filter(
                student=student,
                batch=batch,
                tenant=tenant,
                is_active=True
            ).exclude(id=self.instance.id if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "Student is already actively enrolled in this batch"
                )
        
        return super().validate(attrs)


class BatchListSerializer(ReadOnlyServiceSerializer):
    """
    Optimized serializer for batch lists
    """
    service_class = AcademicService
    
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    student_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = [
            'id', 'name', 'course_name', 'start_date', 'end_date',
            'is_active', 'student_count'
        ]
    
    def get_student_count(self, obj):
        """Get active student count (prefers queryset annotation)."""
        annotated = getattr(obj, 'active_student_count_anno', None)
        if annotated is not None:
            return annotated
        try:
            return obj.batch_students.filter(is_active=True).count()
        except AttributeError:
            return 0


class AcademicReportSerializer(serializers.Serializer):
    """
    Serializer for academic reports
    """
    report_type = serializers.ChoiceField(
        choices=['course_summary', 'batch_enrollment', 'subject_distribution']
    )
    course_id = serializers.UUIDField(required=False, allow_null=True)
    batch_id = serializers.UUIDField(required=False, allow_null=True)
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    
    def validate(self, attrs):
        """Validate report parameters"""
        report_type = attrs.get('report_type')
        
        if report_type == 'batch_enrollment' and not attrs.get('course_id'):
            raise serializers.ValidationError(
                "course_id is required for batch enrollment report"
            )
        
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                "date_from must be before or equal to date_to"
            )
        
        return attrs
    
    def generate_report(self):
        """Generate report using AcademicService"""
        tenant = self.context.get('tenant')
        if not tenant:
            raise serializers.ValidationError("Tenant context required")
        
        service = AcademicService(tenant)
        report_type = self.validated_data['report_type']
        
        if report_type == 'course_summary':
            return service.generate_course_summary()
        elif report_type == 'batch_enrollment':
            course_id = str(self.validated_data['course_id'])
            return service.generate_batch_enrollment_report(course_id)
        elif report_type == 'subject_distribution':
            return service.generate_subject_distribution_report()
        
        raise serializers.ValidationError(f"Unknown report type: {report_type}")


class AcademicYearSerializer(TenantAwareSerializer):
    """
    Academic Year serializer using AcademicService
    """
    service_class = AcademicService
    
    # Computed fields
    applications_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AcademicYear
        fields = [
            'id', 'name', 'start_date', 'end_date', 'is_active',
            'admission_start_date', 'admission_end_date',
            'applications_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'applications_count', 'created_at', 'updated_at']
        extra_kwargs = {
            'name': {'required': True},
            'start_date': {'required': True},
            'end_date': {'required': True},
        }
    
    def get_applications_count(self, obj):
        """Get count of applications for this academic year"""
        try:
            return obj.applications.count()
        except AttributeError:
            return 0
    
    def validate(self, attrs):
        """Validate academic year dates"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError("End date must be after start date")
        
        return super().validate(attrs)


class TimetableSerializer(TenantAwareSerializer):
    """
    Timetable serializer for managing class schedules
    """
    service_class = AcademicService
    
    # Related fields
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    weekday_name = serializers.CharField(source='weekday.weekday', read_only=True)
    timing_name = serializers.CharField(source='class_timing.name', read_only=True)
    timing_display = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Timetable
        fields = [
            'id', 'batch', 'batch_name', 'weekday', 'weekday_name',
            'class_timing', 'timing_name', 'timing_display',
            'subject', 'subject_name', 'employee', 'employee_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'batch_name', 'subject_name', 'weekday_name',
            'timing_name', 'timing_display', 'employee_name',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'batch': {'required': True},
            'weekday': {'required': True},
            'class_timing': {'required': True},
        }
    
    def get_timing_display(self, obj):
        """Get formatted timing display"""
        if obj.class_timing:
            return f"{obj.class_timing.start_time.strftime('%H:%M')} - {obj.class_timing.end_time.strftime('%H:%M')}"
        return ""
    
    def get_employee_name(self, obj):
        """Get employee full name"""
        if obj.employee:
            return f"{obj.employee.first_name} {obj.employee.last_name}"
        return ""


class AttendanceSerializer(TenantAwareSerializer):
    """
    Attendance serializer for managing student attendance
    """
    service_class = AcademicService
    
    # Related fields
    student_name = serializers.SerializerMethodField()
    student_admission_no = serializers.CharField(source='student.admission_no', read_only=True)
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'student', 'student_name', 'student_admission_no',
            'period_table_entry', 'forenoon', 'afternoon', 'reason',
            'month_date', 'batch', 'batch_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'student_name', 'student_admission_no', 'batch_name',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'student': {'required': True},
            'month_date': {'required': True},
            'batch': {'required': True},
        }
    
    def get_student_name(self, obj):
        """Get student full name"""
        if obj.student:
            return f"{obj.student.first_name} {obj.student.last_name}"
        return ""


class WeekdaySerializer(TenantAwareSerializer):
    """
    Weekday serializer
    """
    service_class = AcademicService
    
    class Meta:
        model = Weekday
        fields = ['id', 'weekday', 'day_of_week', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClassTimingSerializer(TenantAwareSerializer):
    """
    Class Timing serializer
    """
    service_class = AcademicService
    
    # Computed fields
    timing_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ClassTiming
        fields = [
            'id', 'batch', 'name', 'start_time', 'end_time',
            'is_break', 'is_deleted', 'timing_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'timing_display', 'created_at', 'updated_at']
        extra_kwargs = {
            'batch': {'required': True},
            'name': {'required': True},
            'start_time': {'required': True},
            'end_time': {'required': True},
        }
    
    def get_timing_display(self, obj):
        """Get formatted timing display"""
        return f"{obj.start_time.strftime('%H:%M')} - {obj.end_time.strftime('%H:%M')}"
    
    def validate(self, attrs):
        """Validate timing data"""
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError("End time must be after start time")
        
        return super().validate(attrs)


class BatchTransferSerializer(serializers.Serializer):
    """
    Serializer for batch transfer operations
    """
    student_id = serializers.UUIDField()
    from_batch_id = serializers.UUIDField()
    to_batch_id = serializers.UUIDField()
    roll_number = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate transfer data"""
        if attrs['from_batch_id'] == attrs['to_batch_id']:
            raise serializers.ValidationError(
                "Source and target batch cannot be the same"
            )
        
        return attrs
    
    def save(self):
        """Perform batch transfer using StudentService"""
        from core.services.student_service import StudentService
        
        tenant = self.context.get('tenant')
        service = StudentService(tenant)
        
        return service.transfer_batch(
            str(self.validated_data['student_id']),
            str(self.validated_data['from_batch_id']),
            str(self.validated_data['to_batch_id']),
            self.validated_data.get('roll_number')
        )