import pytest
import uuid
from datetime import date, timedelta
from django.test import TestCase
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from core.models import (
    Attendance, Student, Batch, Subject, Course, BatchStudent,
    PeriodEntry, ClassTiming, Employee, School
)


@pytest.mark.django_db
class TestAttendanceModel:
    """Test suite for Attendance model.

    These fixtures reuse the session-shared tenant schema from
    tests/conftest.py (the `school` and `academic_year` fixtures) so this suite
    no longer creates a Postgres schema per test. Field names/relations match
    the current models (Subject->Batch, Batch->academic_year, ClassTiming->batch,
    Course has no duration_months).
    """

    @pytest.fixture
    def tenant(self, school):
        """Reuse the session-shared school to avoid per-test schema creation."""
        return school

    @pytest.fixture
    def course(self, tenant):
        """Create a test course"""
        return Course.objects.create(
            course_name="Computer Science",
            code=f"CS{uuid.uuid4().hex[:4].upper()}",
            tenant=tenant,
        )

    @pytest.fixture
    def batch(self, course, academic_year, tenant):
        """Create a test batch"""
        return Batch.objects.create(
            name="CS-2024",
            course=course,
            academic_year=academic_year,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            tenant=tenant,
        )

    @pytest.fixture
    def subject(self, batch, tenant):
        """Create a test subject (linked to a batch)"""
        return Subject.objects.create(
            name="Python Programming",
            code=f"CS{uuid.uuid4().hex[:4].upper()}",
            batch=batch,
            tenant=tenant,
        )

    @pytest.fixture
    def student(self, tenant):
        """Create a test student"""
        return Student.objects.create(
            first_name="John",
            last_name="Doe",
            admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
            admission_date=date.today(),
            date_of_birth=date(2000, 1, 1),
            gender="male",
            tenant=tenant,
        )

    @pytest.fixture
    def employee(self, tenant):
        """Create a test employee"""
        return Employee.objects.create(
            first_name="Teacher",
            last_name="Test",
            employee_number=f"EMP{uuid.uuid4().hex[:6].upper()}",
            joining_date=date.today(),
            gender=True,
            tenant=tenant,
        )

    @pytest.fixture
    def class_timing(self, batch, tenant):
        """Create a test class timing (linked to a batch)"""
        return ClassTiming.objects.create(
            batch=batch,
            name="Period 1",
            start_time="09:00",
            end_time="10:00",
            tenant=tenant,
        )

    @pytest.fixture
    def period_entry(self, batch, subject, class_timing, employee, tenant):
        """Create a test period entry"""
        return PeriodEntry.objects.create(
            month_date=date.today(),
            batch=batch,
            subject=subject,
            class_timing=class_timing,
            employee=employee,
            tenant=tenant,
        )

    def test_attendance_creation_success(self, student, period_entry, batch, tenant):
        """Test successful attendance record creation"""
        attendance = Attendance.objects.create(
            student=student,
            period_table_entry=period_entry,
            forenoon=True,
            afternoon=False,
            reason="Late arrival",
            month_date=date.today(),
            batch=batch,
            tenant=tenant
        )
        
        assert attendance.student == student
        assert attendance.period_table_entry == period_entry
        assert attendance.forenoon is True
        assert attendance.afternoon is False
        assert attendance.reason == "Late arrival"
        assert attendance.month_date == date.today()
        assert attendance.batch == batch
        assert attendance.tenant == tenant
        assert attendance.id is not None
        assert attendance.created_at is not None
        assert attendance.updated_at is not None
    
    def test_attendance_string_representation(self, student, period_entry, batch, tenant):
        """Test the __str__ method of Attendance model"""
        attendance_date = date.today()
        attendance = Attendance.objects.create(
            student=student,
            period_table_entry=period_entry,
            month_date=attendance_date,
            batch=batch,
            tenant=tenant
        )
        
        expected_str = f"{student} - {attendance_date}"
        assert str(attendance) == expected_str
    
    def test_attendance_default_values(self, student, period_entry, batch, tenant):
        """Test default values for attendance fields"""
        attendance = Attendance.objects.create(
            student=student,
            period_table_entry=period_entry,
            month_date=date.today(),
            batch=batch,
            tenant=tenant
        )
        
        # Default values should be False for both sessions
        assert attendance.forenoon is False
        assert attendance.afternoon is False
        assert attendance.reason is None or attendance.reason == ""
    
    def test_attendance_tenant_awareness(self, student, period_entry, batch, tenant):
        """Test that Attendance model is tenant-aware"""
        attendance = Attendance.objects.create(
            student=student,
            period_table_entry=period_entry,
            month_date=date.today(),
            batch=batch,
            tenant=tenant
        )
        
        # Check tenant field is automatically set
        assert attendance.tenant == tenant
        assert hasattr(attendance, 'tenant')  # TenantAwareModel should add tenant field
    
    def test_attendance_foreign_key_relationships(self, student, period_entry, batch, tenant):
        """Test foreign key relationships work correctly"""
        attendance = Attendance.objects.create(
            student=student,
            period_table_entry=period_entry,
            month_date=date.today(),
            batch=batch,
            tenant=tenant
        )
        
        # Test forward relationships
        assert attendance.student.first_name == "John"
        assert attendance.batch.name == "CS-2024"
        assert attendance.period_table_entry.subject.name == "Python Programming"
        
        # Test reverse relationships
        assert attendance in student.attendances.all()
        assert attendance in batch.attendances.all()
        assert attendance in period_entry.attendances.all()
    
    def test_attendance_database_indexes(self, student, period_entry, batch, tenant):
        """Test that database indexes are properly created"""
        # Create multiple attendance records to test index performance
        attendance_dates = [date.today() - timedelta(days=i) for i in range(5)]
        
        attendances = []
        for attendance_date in attendance_dates:
            attendance = Attendance.objects.create(
                student=student,
                period_table_entry=period_entry,
                month_date=attendance_date,
                batch=batch,
                tenant=tenant
            )
            attendances.append(attendance)
        
        # Test queries that should benefit from indexes
        # Index on tenant
        tenant_filtered = Attendance.objects.filter(tenant=tenant)
        assert tenant_filtered.count() == 5
        
        # Index on month_date, batch
        date_batch_filtered = Attendance.objects.filter(
            month_date=date.today(),
            batch=batch
        )
        assert date_batch_filtered.count() == 1
        
        # Index on student, batch
        student_batch_filtered = Attendance.objects.filter(
            student=student,
            batch=batch
        )
        assert student_batch_filtered.count() == 5
    
    def test_attendance_bulk_operations(self, student, period_entry, batch, tenant):
        """Test bulk create and update operations"""
        attendance_dates = [date.today() - timedelta(days=i) for i in range(10)]
        
        # Bulk create
        attendances_to_create = [
            Attendance(
                student=student,
                period_table_entry=period_entry,
                month_date=attendance_date,
                batch=batch,
                forenoon=True,
                afternoon=i % 2 == 0,
                tenant=tenant
            )
            for i, attendance_date in enumerate(attendance_dates)
        ]
        
        created_attendances = Attendance.objects.bulk_create(attendances_to_create)
        assert len(created_attendances) == 10
        
        # Verify all were created
        total_count = Attendance.objects.filter(student=student).count()
        assert total_count == 10
        
        # Test bulk update
        Attendance.objects.filter(student=student).update(reason="Bulk updated")
        
        updated_attendances = Attendance.objects.filter(student=student)
        for attendance in updated_attendances:
            assert attendance.reason == "Bulk updated"
    
    def test_attendance_filtering_and_ordering(self, tenant, academic_year):
        """Test complex filtering and ordering operations"""
        # Create test data
        course = Course.objects.create(course_name="Test Course", code=f"TC{uuid.uuid4().hex[:4].upper()}", tenant=tenant)
        batch1 = Batch.objects.create(name="TC-2024-A", course=course, academic_year=academic_year, start_date=date.today(), end_date=date.today() + timedelta(days=365), tenant=tenant)
        batch2 = Batch.objects.create(name="TC-2024-B", course=course, academic_year=academic_year, start_date=date.today(), end_date=date.today() + timedelta(days=365), tenant=tenant)

        subject = Subject.objects.create(name="Test Subject", code=f"TS{uuid.uuid4().hex[:4].upper()}", batch=batch1, tenant=tenant)
        employee = Employee.objects.create(first_name="Test", last_name="Teacher", employee_number=f"TT{uuid.uuid4().hex[:4].upper()}", joining_date=date.today(), gender=True, tenant=tenant)
        class_timing = ClassTiming.objects.create(batch=batch1, name="Period 1", start_time="09:00", end_time="10:00", tenant=tenant)

        students = []
        for i in range(3):
            student = Student.objects.create(
                first_name=f"Student{i}",
                last_name="Test",
                admission_no=f"TADM{uuid.uuid4().hex[:5].upper()}",
                admission_date=date.today(),
                date_of_birth=date(2000, 1, 1),
                gender="male",
                tenant=tenant
            )
            students.append(student)
        
        period_entry = PeriodEntry.objects.create(
            month_date=date.today(),
            batch=batch1,
            subject=subject,
            class_timing=class_timing,
            employee=employee,
            tenant=tenant
        )
        
        # Create attendance records
        for i, student in enumerate(students):
            for j, batch in enumerate([batch1, batch2]):
                Attendance.objects.create(
                    student=student,
                    period_table_entry=period_entry,
                    month_date=date.today() - timedelta(days=j),
                    batch=batch,
                    forenoon=i % 2 == 0,
                    afternoon=j % 2 == 0,
                    reason=f"Reason {i}-{j}",
                    tenant=tenant
                )
        
        # Test complex filtering (scoped to this test's tenant; core models are
        # shared-schema so an unscoped query would see every tenant's data)
        present_forenoon = Attendance.objects.filter(tenant=tenant, forenoon=True)
        assert present_forenoon.count() == 4  # 2 students * 2 batches

        batch1_attendance = Attendance.objects.filter(batch=batch1)
        assert batch1_attendance.count() == 3  # 3 students in batch1

        student0_attendance = Attendance.objects.filter(student=students[0])
        assert student0_attendance.count() == 2  # Student0 in 2 batches

        # Test ordering
        ordered_by_date = Attendance.objects.filter(tenant=tenant).order_by('-month_date')
        dates = [att.month_date for att in ordered_by_date]
        assert dates == sorted(dates, reverse=True)

        ordered_by_student = Attendance.objects.filter(tenant=tenant).order_by('student__first_name')
        student_names = [att.student.first_name for att in ordered_by_student]
        assert student_names == sorted(student_names)
    
    def test_attendance_cascade_deletes(self, student, period_entry, batch, tenant):
        """Test cascade deletion behavior"""
        attendance = Attendance.objects.create(
            student=student,
            period_table_entry=period_entry,
            month_date=date.today(),
            batch=batch,
            tenant=tenant
        )
        
        attendance_id = attendance.id
        
        # Delete student should cascade delete attendance
        student.delete()
        
        with pytest.raises(Attendance.DoesNotExist):
            Attendance.objects.get(id=attendance_id)
    
    def test_attendance_date_queries(self, student, period_entry, batch, tenant):
        """Test date-based queries on attendance"""
        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        
        # Create attendance records for different dates
        Attendance.objects.create(
            student=student, period_table_entry=period_entry,
            month_date=yesterday, batch=batch, tenant=tenant
        )
        Attendance.objects.create(
            student=student, period_table_entry=period_entry,
            month_date=today, batch=batch, tenant=tenant
        )
        
        # Test date filtering (scoped to this test's tenant - shared schema)
        today_attendance = Attendance.objects.filter(tenant=tenant, month_date=today)
        assert today_attendance.count() == 1

        yesterday_attendance = Attendance.objects.filter(tenant=tenant, month_date=yesterday)
        assert yesterday_attendance.count() == 1

        # Test date range queries
        recent_attendance = Attendance.objects.filter(
            tenant=tenant,
            month_date__gte=yesterday,
            month_date__lte=today
        )
        assert recent_attendance.count() == 2

        # Test future date filtering
        future_attendance = Attendance.objects.filter(tenant=tenant, month_date=tomorrow)
        assert future_attendance.count() == 0
    
    def test_attendance_reason_field(self, student, period_entry, batch, tenant):
        """Test the reason field behavior"""
        # Test with no reason
        attendance1 = Attendance.objects.create(
            student=student,
            period_table_entry=period_entry,
            month_date=date.today(),
            batch=batch,
            tenant=tenant
        )
        assert attendance1.reason is None or attendance1.reason == ""
        
        # Test with reason
        attendance2 = Attendance.objects.create(
            student=student,
            period_table_entry=period_entry,
            month_date=date.today() - timedelta(days=1),
            batch=batch,
            reason="Medical leave",
            tenant=tenant
        )
        assert attendance2.reason == "Medical leave"
        
        # Test with long reason (up to 255 chars)
        long_reason = "A" * 255
        attendance3 = Attendance.objects.create(
            student=student,
            period_table_entry=period_entry,
            month_date=date.today() - timedelta(days=2),
            batch=batch,
            reason=long_reason,
            tenant=tenant
        )
        assert attendance3.reason == long_reason
    
    def test_attendance_session_combinations(self, student, period_entry, batch, tenant):
        """Test different combinations of forenoon/afternoon attendance"""
        test_cases = [
            (True, True, "Full day present"),
            (False, False, "Full day absent"),
            (True, False, "Half day - morning present"),
            (False, True, "Half day - afternoon present")
        ]
        
        attendances = []
        for i, (forenoon, afternoon, description) in enumerate(test_cases):
            attendance = Attendance.objects.create(
                student=student,
                period_table_entry=period_entry,
                month_date=date.today() - timedelta(days=i),
                batch=batch,
                forenoon=forenoon,
                afternoon=afternoon,
                reason=description,
                tenant=tenant
            )
            attendances.append(attendance)
        
        # Verify all combinations were created correctly
        for attendance, (forenoon, afternoon, description) in zip(attendances, test_cases):
            assert attendance.forenoon == forenoon
            assert attendance.afternoon == afternoon
            assert attendance.reason == description
        
        # Test filtering by session (scoped to this test's tenant - shared schema)
        full_present = Attendance.objects.filter(tenant=tenant, forenoon=True, afternoon=True)
        assert full_present.count() == 1

        full_absent = Attendance.objects.filter(tenant=tenant, forenoon=False, afternoon=False)
        assert full_absent.count() == 1

        from django.db import models
        partial_present = Attendance.objects.filter(
            models.Q(forenoon=True, afternoon=False) |
            models.Q(forenoon=False, afternoon=True),
            tenant=tenant,
        )
        assert partial_present.count() == 2


@pytest.mark.django_db  
class TestAttendanceModelEdgeCases:
    """Test edge cases and error conditions for Attendance model"""
    
    @pytest.fixture
    def minimal_setup(self, school, academic_year):
        """Create minimal required objects (reusing the session-shared school)."""
        tenant = school
        suffix = uuid.uuid4().hex[:4].upper()
        course = Course.objects.create(course_name="Edge Course", code=f"EC{suffix}", tenant=tenant)
        batch = Batch.objects.create(name="EC-2024", course=course, academic_year=academic_year, start_date=date.today(), end_date=date.today() + timedelta(days=365), tenant=tenant)
        subject = Subject.objects.create(name="Edge Subject", code=f"ES{suffix}", batch=batch, tenant=tenant)
        student = Student.objects.create(first_name="Edge", last_name="Student", admission_no=f"EADM{suffix}", admission_date=date.today(), date_of_birth=date(2000, 1, 1), gender="male", tenant=tenant)
        employee = Employee.objects.create(first_name="Edge", last_name="Teacher", employee_number=f"ETE{suffix}", joining_date=date.today(), gender=True, tenant=tenant)
        class_timing = ClassTiming.objects.create(batch=batch, name="Period 1", start_time="09:00", end_time="10:00", tenant=tenant)
        period_entry = PeriodEntry.objects.create(month_date=date.today(), batch=batch, subject=subject, class_timing=class_timing, employee=employee, tenant=tenant)

        return {
            'tenant': tenant,
            'academic_year': academic_year,
            'batch': batch,
            'subject': subject,
            'student': student,
            'period_entry': period_entry
        }
    
    def test_attendance_without_required_fields(self, minimal_setup):
        """Test creating attendance without required fields.

        student, batch and month_date are NOT NULL; period_table_entry is
        nullable (on_delete=SET_NULL, null=True) so it is intentionally NOT
        required. Each failing create is wrapped in its own savepoint because a
        DB-level IntegrityError aborts the surrounding test transaction.
        """
        setup = minimal_setup

        # Missing student
        with pytest.raises(IntegrityError), transaction.atomic():
            Attendance.objects.create(
                period_table_entry=setup['period_entry'],
                month_date=date.today(),
                batch=setup['batch'],
                tenant=setup['tenant']
            )

        # Missing batch
        with pytest.raises(IntegrityError), transaction.atomic():
            Attendance.objects.create(
                student=setup['student'],
                period_table_entry=setup['period_entry'],
                month_date=date.today(),
                tenant=setup['tenant']
            )

        # Missing month_date
        with pytest.raises(IntegrityError), transaction.atomic():
            Attendance.objects.create(
                student=setup['student'],
                period_table_entry=setup['period_entry'],
                batch=setup['batch'],
                tenant=setup['tenant']
            )

        # period_table_entry is optional: creating without it must succeed.
        ok = Attendance.objects.create(
            student=setup['student'],
            month_date=date.today(),
            batch=setup['batch'],
            tenant=setup['tenant'],
        )
        assert ok.period_table_entry is None
    
    def test_attendance_with_extreme_dates(self, minimal_setup):
        """Test attendance with extreme date values"""
        setup = minimal_setup
        
        # Test very old date
        old_date = date(1900, 1, 1)
        old_attendance = Attendance.objects.create(
            student=setup['student'],
            period_table_entry=setup['period_entry'],
            month_date=old_date,
            batch=setup['batch'],
            tenant=setup['tenant']
        )
        assert old_attendance.month_date == old_date
        
        # Test far future date
        future_date = date(2100, 12, 31)
        future_attendance = Attendance.objects.create(
            student=setup['student'],
            period_table_entry=setup['period_entry'],
            month_date=future_date,
            batch=setup['batch'],
            tenant=setup['tenant']
        )
        assert future_attendance.month_date == future_date
    
    def test_attendance_reason_edge_cases(self, minimal_setup):
        """Test reason field with edge cases"""
        setup = minimal_setup
        
        # Test empty string
        empty_reason = Attendance.objects.create(
            student=setup['student'],
            period_table_entry=setup['period_entry'],
            month_date=date.today(),
            batch=setup['batch'],
            reason="",
            tenant=setup['tenant']
        )
        assert empty_reason.reason == ""
        
        # Test maximum length reason
        max_reason = "A" * 255
        max_length_attendance = Attendance.objects.create(
            student=setup['student'],
            period_table_entry=setup['period_entry'],
            month_date=date.today() - timedelta(days=1),
            batch=setup['batch'],
            reason=max_reason,
            tenant=setup['tenant']
        )
        assert max_length_attendance.reason == max_reason
        
        # Test reason with special characters
        special_reason = "Medical 🏥 leave - fever & cold (37.5°C)"
        special_attendance = Attendance.objects.create(
            student=setup['student'],
            period_table_entry=setup['period_entry'],
            month_date=date.today() - timedelta(days=2),
            batch=setup['batch'],
            reason=special_reason,
            tenant=setup['tenant']
        )
        assert special_attendance.reason == special_reason
    
    def test_attendance_query_performance(self, minimal_setup):
        """Test query performance with large dataset"""
        setup = minimal_setup
        
        # Create multiple students, batches, and attendance records
        students = []
        batches = []
        
        for i in range(10):
            student = Student.objects.create(
                first_name=f"Student{i}",
                last_name="Performance",
                admission_no=f"PADM{i:03d}",
                admission_date=date.today(),
                date_of_birth=date(2000, 1, 1),
                gender="male",
                tenant=setup['tenant']
            )
            students.append(student)
            
            batch = Batch.objects.create(
                name=f"PERF-{i}",
                course=setup['batch'].course,
                academic_year=setup['academic_year'],
                start_date=date.today(),
                end_date=date.today() + timedelta(days=365),
                tenant=setup['tenant']
            )
            batches.append(batch)
        
        # Create attendance records (10 students * 10 batches * 30 days = 3000 records)
        attendance_records = []
        for student in students:
            for batch in batches:
                for day in range(30):
                    attendance_records.append(
                        Attendance(
                            student=student,
                            period_table_entry=setup['period_entry'],
                            month_date=date.today() - timedelta(days=day),
                            batch=batch,
                            forenoon=day % 2 == 0,
                            afternoon=day % 3 == 0,
                            tenant=setup['tenant']
                        )
                    )
        
        # Bulk create for better performance
        Attendance.objects.bulk_create(attendance_records)
        
        # Test various queries that should be fast due to indexes
        import time
        
        # Query by tenant (should use tenant index)
        start_time = time.time()
        tenant_records = Attendance.objects.filter(tenant=setup['tenant']).count()
        tenant_time = time.time() - start_time
        assert tenant_records == 3000
        assert tenant_time < 1.0  # Should complete within 1 second
        
        # Query by date and batch (should use date_batch index)
        start_time = time.time()
        date_batch_records = Attendance.objects.filter(
            month_date=date.today(),
            batch=batches[0]
        ).count()
        date_batch_time = time.time() - start_time
        assert date_batch_records == 10  # 10 students in batch
        assert date_batch_time < 1.0
        
        # Query by student and batch (should use student_batch index)
        start_time = time.time()
        student_batch_records = Attendance.objects.filter(
            student=students[0],
            batch=batches[0]
        ).count()
        student_batch_time = time.time() - start_time
        assert student_batch_records == 30  # 30 days
        assert student_batch_time < 1.0
    
    def test_attendance_model_meta_properties(self):
        """Test model meta properties and configuration"""
        meta = Attendance._meta
        
        # Test indexes
        index_names = [idx.name for idx in meta.indexes if idx.name]
        
        # Should have tenant index
        tenant_indexes = [idx for idx in meta.indexes if 'tenant' in idx.fields]
        assert len(tenant_indexes) >= 1
        
        # Should have date_batch index
        date_batch_indexes = [idx for idx in meta.indexes if 'month_date' in idx.fields and 'batch' in idx.fields]
        assert len(date_batch_indexes) >= 1
        
        # Should have student_batch index
        student_batch_indexes = [idx for idx in meta.indexes if 'student' in idx.fields and 'batch' in idx.fields]
        assert len(student_batch_indexes) >= 1
        
        # Test field properties
        from django.db import models
        student_field = meta.get_field('student')
        assert student_field.related_model == Student
        assert student_field.remote_field.on_delete == models.CASCADE

        batch_field = meta.get_field('batch')
        assert batch_field.related_model == Batch
        assert batch_field.remote_field.on_delete == models.CASCADE
        
        forenoon_field = meta.get_field('forenoon')
        assert forenoon_field.default is False
        
        afternoon_field = meta.get_field('afternoon')
        assert afternoon_field.default is False
        
        reason_field = meta.get_field('reason')
        assert reason_field.max_length == 255
        assert reason_field.blank is True
        assert reason_field.null is True