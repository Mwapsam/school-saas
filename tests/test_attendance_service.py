import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch
from django.test import TestCase
from django.db import transaction
from django.db.models import Q

from core.models import (
    Attendance, Student, Batch, Subject, Course, BatchStudent,
    PeriodEntry, ClassTiming, Employee, School, Event, Term
)
from core.services.attendance_service import AttendanceService
from core.services.exceptions import ValidationException, NotFoundException


def _nearest_school_day(base: date = None) -> date:
    """Walk back to the nearest Mon-Fri so AttendanceService's is_school_day
    gate doesn't reject test dates that happen to fall on a weekend."""
    d = base or date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _prev_school_day(base: date) -> date:
    """Return the school day immediately before `base` (skipping weekends)."""
    d = base - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


@pytest.mark.django_db
class TestAttendanceService:
    """Test suite for AttendanceService functionality"""
    
    @pytest.fixture
    def tenant(self):
        """Create a test tenant tenant"""
        return School.objects.create(
            name="Test tenant",
            code="TEST001",
            schema_name="test_svc001"
        )
    
    @pytest.fixture
    def academic_year(self, tenant):
        """Create a test academic year"""
        from core.models import AcademicYear
        return AcademicYear.objects.create(
            name="2024-2025",
            start_date=date.today() - timedelta(days=60),
            end_date=date.today() + timedelta(days=300),
            tenant=tenant
        )

    @pytest.fixture
    def term(self, tenant, academic_year):
        """Term covering today's date (required for attendance marking gate)."""
        return Term.objects.create(
            tenant=tenant,
            academic_year=academic_year,
            name='Test Term',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            order=1,
        )

    @pytest.fixture
    def course(self, tenant):
        """Create a test course"""
        return Course.objects.create(
            course_name="Computer Science",
            code="CS",
            tenant=tenant
        )
    
    @pytest.fixture
    def batch(self, course, academic_year, tenant, term):
        """Create a test batch"""
        return Batch.objects.create(
            name="CS-2024",
            course=course,
            academic_year=academic_year,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            tenant=tenant
        )
    
    @pytest.fixture
    def subject(self, batch, tenant):
        """Create a test subject"""
        return Subject.objects.create(
            name="Python Programming",
            code="CS101",
            batch=batch,
            tenant=tenant
        )
    
    @pytest.fixture
    def student(self, tenant):
        """Create a test student"""
        return Student.objects.create(
            first_name="John",
            last_name="Doe",
            admission_no="ADM001",
            admission_date=date.today(),
            date_of_birth=date(2000, 1, 1),
            gender="male",
            tenant=tenant
        )
    
    @pytest.fixture
    def employee(self, tenant):
        """Create a test employee"""
        return Employee.objects.create(
            first_name="Teacher",
            last_name="Test",
            employee_number="EMP001",
            joining_date=date.today(),
            gender=True,
            tenant=tenant
        )
    
    @pytest.fixture
    def class_timing(self, batch, tenant):
        """Create a test class timing (linked to a batch)"""
        return ClassTiming.objects.create(
            batch=batch,
            name="Period 1",
            start_time="09:00",
            end_time="10:00",
            tenant=tenant
        )
    
    @pytest.fixture
    def batch_student(self, batch, student, tenant):
        """Create a batch-student relationship"""
        return BatchStudent.objects.create(
            batch=batch,
            student=student,
            roll_number="001",
            tenant=tenant
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
            tenant=tenant
        )
    
    @pytest.fixture
    def attendance_service(self, tenant):
        """Create an AttendanceService instance"""
        return AttendanceService(tenant)
    
    def test_record_student_attendance_success(self, attendance_service, student, batch, subject, batch_student):
        """Test successful attendance recording"""
        attendance_date = _nearest_school_day()
        
        result = attendance_service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(batch.id),
            attendance_date=attendance_date,
            forenoon=True,
            afternoon=True,
            reason="Present"
        )

        assert result is not None
        assert result.student == student
        assert result.batch == batch
        assert result.forenoon is True
        assert result.afternoon is True
        assert result.month_date == attendance_date
    
    def test_record_student_attendance_update_existing(self, attendance_service, student, batch, subject, batch_student):
        """Test updating existing attendance record"""
        attendance_date = _nearest_school_day()
        
        # Create initial attendance record
        first_result = attendance_service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(batch.id),
            attendance_date=attendance_date,
            forenoon=True,
            afternoon=True,
        )

        # Update the same record
        updated_result = attendance_service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(batch.id),
            attendance_date=attendance_date,
            forenoon=False,
            afternoon=False,
            reason="Sick"
        )

        assert updated_result.id == first_result.id
        assert updated_result.forenoon is False
        assert updated_result.afternoon is False
        assert updated_result.reason == "Sick"
    
    def test_record_attendance_student_not_found(self, attendance_service, batch, subject):
        """Test recording attendance for non-existent student"""
        fake_student_id = "00000000-0000-0000-0000-000000000000"
        
        with pytest.raises(NotFoundException) as exc_info:
            attendance_service.record_student_attendance(
                student_id=fake_student_id,
                batch_id=str(batch.id),
                attendance_date=_nearest_school_day(),
                forenoon=True,
                afternoon=True,
            )

        assert f"Student with id {fake_student_id} not found" in str(exc_info.value)
    
    def test_record_attendance_batch_not_found(self, attendance_service, student, subject):
        """Test recording attendance for non-existent batch"""
        fake_batch_id = "00000000-0000-0000-0000-000000000000"
        
        with pytest.raises(NotFoundException) as exc_info:
            attendance_service.record_student_attendance(
                student_id=str(student.id),
                batch_id=fake_batch_id,
                attendance_date=_nearest_school_day(),
                forenoon=True,
                afternoon=True,
            )

        assert f"Batch with id {fake_batch_id} not found" in str(exc_info.value)
    
    def test_record_attendance_student_not_in_batch(self, attendance_service, student, batch, tenant):
        """Test recording attendance for a student not enrolled in the batch.

        (No batch_student fixture here, so the student is not enrolled.) The
        implementation's attendance recording is subject-agnostic, so the former
        subject_not_found / subject_not_in_batch cases no longer apply.
        """
        with pytest.raises(ValidationException) as exc_info:
            attendance_service.record_student_attendance(
                student_id=str(student.id),
                batch_id=str(batch.id),
                attendance_date=_nearest_school_day(),
                forenoon=True,
                afternoon=True,
            )

        assert f"Student {student.first_name} {student.last_name} is not enrolled in batch {batch.name}" in str(exc_info.value)

    def test_record_student_attendance_rejects_weekend(self, attendance_service, student, batch, batch_student):
        """Marking attendance on a weekend must be rejected, not silently recorded."""
        d = date.today()
        while d.weekday() < 5:
            d += timedelta(days=1)  # walk forward to the nearest Sat/Sun

        with pytest.raises(ValidationException) as exc_info:
            attendance_service.record_student_attendance(
                student_id=str(student.id),
                batch_id=str(batch.id),
                attendance_date=d,
                forenoon=True,
                afternoon=True,
            )
        assert "not a school day" in str(exc_info.value)
        assert not Attendance.objects.filter(student=student, batch=batch, month_date=d).exists()

    def test_record_student_attendance_rejects_holiday(self, attendance_service, student, batch, batch_student, academic_year, tenant):
        """Marking attendance on a date covered by a holiday Event must be rejected."""
        holiday_date = _nearest_school_day()
        Event.objects.create(
            tenant=tenant,
            academic_year=academic_year,
            title="Public Holiday",
            start_date=f"{holiday_date} 00:00:00",
            end_date=f"{holiday_date} 23:59:59",
            is_holiday=True,
        )

        with pytest.raises(ValidationException) as exc_info:
            attendance_service.record_student_attendance(
                student_id=str(student.id),
                batch_id=str(batch.id),
                attendance_date=holiday_date,
                forenoon=True,
                afternoon=True,
            )
        assert "not a school day" in str(exc_info.value)
        assert not Attendance.objects.filter(student=student, batch=batch, month_date=holiday_date).exists()

    def test_mark_batch_attendance_rejects_non_school_day(self, attendance_service, student, batch, batch_student):
        """Bulk marking must also be rejected for non-school days."""
        d = date.today()
        while d.weekday() < 5:
            d += timedelta(days=1)

        with pytest.raises(ValidationException):
            attendance_service.mark_batch_attendance(
                str(batch.id),
                d.strftime('%Y-%m-%d'),
                [{'student_id': str(student.id), 'forenoon': True, 'afternoon': True, 'reason': ''}],
            )
        assert not Attendance.objects.filter(student=student, batch=batch, month_date=d).exists()

    def test_get_attendance_statistics_all_params(self, attendance_service, student, batch, subject, batch_student):
        """Test getting attendance statistics with all parameters"""
        attendance_date = _nearest_school_day()
        prev_day = _prev_school_day(attendance_date)
        start_date = attendance_date - timedelta(days=7)
        end_date = attendance_date + timedelta(days=7)

        # Create some attendance records (present == forenoon OR afternoon)
        attendance_service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(batch.id),
            attendance_date=attendance_date,
            forenoon=True,
            afternoon=True,
        )

        attendance_service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(batch.id),
            attendance_date=prev_day,
            forenoon=False,
            afternoon=False,
            reason="Sick"
        )
        
        stats = attendance_service.get_attendance_statistics(
            student_id=str(student.id),
            batch_id=str(batch.id),
            start_date=start_date,
            end_date=end_date
        )
        
        assert stats['total_records'] == 2
        assert stats['present_count'] == 1
        assert stats['absent_count'] == 1
        assert stats['attendance_rate'] == 50.0
        assert stats['period_start'] == start_date
        assert stats['period_end'] == end_date
    
    def test_get_attendance_statistics_no_records(self, attendance_service, student, batch):
        """Test getting attendance statistics when no records exist"""
        stats = attendance_service.get_attendance_statistics(
            student_id=str(student.id),
            batch_id=str(batch.id)
        )
        
        assert stats['total_records'] == 0
        assert stats['present_count'] == 0
        assert stats['absent_count'] == 0
        assert stats['attendance_rate'] == 0
    
    def test_get_daily_attendance_summary(self, attendance_service, student, batch, subject, batch_student):
        """Test getting daily attendance summary"""
        today = _nearest_school_day()
        
        # Create attendance record for today
        attendance_service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(batch.id),
            attendance_date=today,
            forenoon=True,
            afternoon=True,
        )

        summary = attendance_service.get_daily_attendance_summary(today)
        
        assert summary['total_records'] == 1
        assert summary['present_count'] == 1
        assert summary['absent_count'] == 0
        assert summary['attendance_rate'] == 100.0
    
    def test_get_student_attendance_summary(self, attendance_service, student, batch, subject, batch_student):
        """Test getting student attendance summary over period"""
        # Build 5 consecutive school days (skipping weekends) ending at the
        # nearest school day, most recent first, so every date fed into
        # record_student_attendance passes the is_school_day gate.
        school_days = []
        d = _nearest_school_day()
        while len(school_days) < 5:
            if d.weekday() < 5:
                school_days.append(d)
            d -= timedelta(days=1)

        # Create multiple attendance records (present == forenoon OR afternoon)
        for i in range(5):
            present = i % 2 == 0  # Alternating present/absent
            attendance_service.record_student_attendance(
                student_id=str(student.id),
                batch_id=str(batch.id),
                attendance_date=school_days[i],
                forenoon=present,
                afternoon=present,
            )
        
        summary = attendance_service.get_student_attendance_summary(str(student.id), days=7)
        
        assert summary['total_records'] == 5
        assert summary['present_count'] == 3
        assert summary['absent_count'] == 2
        assert summary['attendance_rate'] == 60.0
        assert summary['present_days'] == 3
        assert summary['absent_days'] == 2
        assert summary['attendance_percentage'] == 60.0
    
    def test_search_attendance_with_query(self, attendance_service, student, batch, subject, batch_student):
        """Test searching attendance with text query"""
        attendance_service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(batch.id),
            attendance_date=_nearest_school_day(),
            forenoon=True,
            afternoon=True,
        )
        
        # Search by student first name
        results = attendance_service.search_attendance(query="John")
        assert results.count() == 1
        
        # Search by student last name
        results = attendance_service.search_attendance(query="Doe")
        assert results.count() == 1
        
        # Search by batch name
        results = attendance_service.search_attendance(query="CS-2024")
        assert results.count() == 1
        
        # Search with no matches
        results = attendance_service.search_attendance(query="NonExistent")
        assert results.count() == 0
    
    def test_search_attendance_with_date_filters(self, attendance_service, student, batch, subject, batch_student):
        """Test searching attendance with date filters"""
        today = _nearest_school_day()
        yesterday = _prev_school_day(today)
        
        # Create attendance records on different dates
        attendance_service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(batch.id),
            attendance_date=today,
            forenoon=True,
            afternoon=True,
        )

        attendance_service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(batch.id),
            attendance_date=yesterday,
            forenoon=False,
            afternoon=False,
        )
        
        # Filter by start date
        results = attendance_service.search_attendance(start_date=today)
        assert results.count() == 1
        
        # Filter by end date
        results = attendance_service.search_attendance(end_date=yesterday)
        assert results.count() == 1
        
        # Filter by date range
        results = attendance_service.search_attendance(start_date=yesterday, end_date=today)
        assert results.count() == 2
    
    def test_validate_create_data_missing_fields(self, attendance_service):
        """Test validation of create data with missing required fields"""
        # Test missing student
        with pytest.raises(ValidationException) as exc_info:
            attendance_service._validate_create_data({'batch': 'test', 'subject': 'test', 'month_date': date.today()})
        assert "Required field 'student' is missing" in str(exc_info.value)
        
        # Test missing batch
        with pytest.raises(ValidationException) as exc_info:
            attendance_service._validate_create_data({'student': 'test', 'subject': 'test', 'month_date': date.today()})
        assert "Required field 'batch' is missing" in str(exc_info.value)
        
        # Test missing subject
        with pytest.raises(ValidationException) as exc_info:
            attendance_service._validate_create_data({'student': 'test', 'batch': 'test', 'month_date': date.today()})
        assert "Required field 'subject' is missing" in str(exc_info.value)
        
        # Test missing month_date
        with pytest.raises(ValidationException) as exc_info:
            attendance_service._validate_create_data({'student': 'test', 'batch': 'test', 'subject': 'test'})
        assert "Required field 'month_date' is missing" in str(exc_info.value)
    
    def test_validate_create_data_future_date(self, attendance_service):
        """Test validation prevents future attendance dates"""
        future_date = date.today() + timedelta(days=1)
        
        with pytest.raises(ValidationException) as exc_info:
            attendance_service._validate_create_data({
                'student': 'test',
                'batch': 'test',
                'subject': 'test',
                'month_date': future_date
            })
        assert "Attendance date cannot be in the future" in str(exc_info.value)
    
    def test_get_attendance_context(self, attendance_service, batch, student, batch_student):
        """Test getting attendance context data"""
        # Create another batch to test filtering
        batch2 = Batch.objects.create(
            name="CS-2025",
            course=batch.course,
            academic_year=batch.academic_year,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            tenant=attendance_service.tenant
        )
        
        context = attendance_service.get_attendance_context()
        
        assert 'batches' in context
        assert 'total_records' in context
        assert context['batches'].count() == 2  # Both batches should be included
        assert context['total_records'] == 0  # No attendance records yet
    
    @pytest.mark.slow
    def test_bulk_attendance_operations_performance(self, attendance_service, tenant, academic_year):
        """Test performance with bulk attendance operations"""
        Term.objects.create(
            tenant=tenant,
            academic_year=academic_year,
            name='Bulk Test Term',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            order=1,
        )
        course = Course.objects.create(course_name="Bulk Test", code="BT", tenant=tenant)
        batch = Batch.objects.create(name="BT-2024", course=course, academic_year=academic_year, start_date=date.today(), end_date=date.today() + timedelta(days=365), tenant=tenant)
        subject = Subject.objects.create(name="Bulk Subject", code="BS101", batch=batch, tenant=tenant)
        
        # Create 50 students
        students = []
        for i in range(50):
            student = Student.objects.create(
                first_name=f"Student{i}",
                last_name="Test",
                admission_no=f"ADM{i:03d}",
                admission_date=date.today(),
                date_of_birth=date(2000, 1, 1),
                gender="male",
                tenant=tenant
            )
            students.append(student)
            BatchStudent.objects.create(batch=batch, student=student, roll_number=f"{i:03d}", tenant=tenant)
        
        # Record attendance for all students - this should complete quickly
        attendance_date = _nearest_school_day()
        start_time = datetime.now()
        for student in students:
            attendance_service.record_student_attendance(
                student_id=str(student.id),
                batch_id=str(batch.id),
                attendance_date=attendance_date,
                forenoon=True,
                afternoon=True,
            )
        end_time = datetime.now()

        # Should complete within reasonable time (adjust threshold as needed)
        duration = (end_time - start_time).total_seconds()
        assert duration < 30  # Should complete within 30 seconds

        # Verify all records were created
        total_records = Attendance.objects.filter(batch=batch, month_date=attendance_date).count()
        assert total_records == 50


@pytest.mark.django_db
class TestAttendanceServiceAdvanced:
    """Advanced test cases for AttendanceService"""
    
    @pytest.fixture
    def setup_full_data(self, db):
        """Set up complete test data environment"""
        from core.models import AcademicYear
        tenant = School.objects.create(name="Advanced Test tenant", code="ADV001", schema_name="test_adv001")
        academic_year = AcademicYear.objects.create(name="2024-2025", start_date=date.today() - timedelta(days=60), end_date=date.today() + timedelta(days=300), tenant=tenant)
        Term.objects.create(
            tenant=tenant,
            academic_year=academic_year,
            name='Advanced Term',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            order=1,
        )
        course = Course.objects.create(course_name="Advanced CS", code="ACS", tenant=tenant)
        batch = Batch.objects.create(name="ACS-2024", course=course, academic_year=academic_year, start_date=date.today() - timedelta(days=60), end_date=date.today() + timedelta(days=300), tenant=tenant)
        subject = Subject.objects.create(name="Advanced Programming", code="ACS201", batch=batch, tenant=tenant)
        
        students = []
        for i in range(10):
            student = Student.objects.create(
                first_name=f"Advanced{i}",
                last_name="Student",
                admission_no=f"AADM{i:03d}",
                admission_date=date.today(),
                date_of_birth=date(1999, 1, 1),
                gender="male",
                tenant=tenant
            )
            students.append(student)
            BatchStudent.objects.create(batch=batch, student=student, roll_number=f"A{i:03d}", tenant=tenant)
        
        employee = Employee.objects.create(first_name="Advanced", last_name="Teacher", employee_number="AEMP001", joining_date=date.today(), gender=True, tenant=tenant)
        class_timing = ClassTiming.objects.create(batch=batch, name="Period 1", start_time="09:00", end_time="10:00", tenant=tenant)
        
        return {
            'tenant': tenant,
            'course': course,
            'batch': batch,
            'subject': subject,
            'students': students,
            'employee': employee,
            'class_timing': class_timing
        }
    
    def test_batch_attendance_operations(self, setup_full_data):
        """Test batch-level attendance operations"""
        data = setup_full_data
        service = AttendanceService(data['tenant'])
        target_date = _nearest_school_day()

        # Test getting batch attendance for date (initially empty)
        result = service.get_batch_attendance_for_date(str(data['batch'].id), target_date.strftime('%Y-%m-%d'))
        
        assert result['batch'] == data['batch']
        assert result['total_students'] == 10
        assert len(result['students']) == 10
        
        # Test marking batch attendance
        attendance_records = []
        for i, student in enumerate(data['students']):
            attendance_records.append({
                'student_id': str(student.id),
                'forenoon': i % 2 == 0,  # Alternating attendance
                'afternoon': True,
                'reason': 'Sick' if i % 2 == 1 else ''
            })
        
        updated_records = service.mark_batch_attendance(
            str(data['batch'].id),
            target_date.strftime('%Y-%m-%d'),
            attendance_records
        )
        
        assert len(updated_records) == 10
        for i, record in enumerate(updated_records):
            assert record['forenoon'] == (i % 2 == 0)
            assert record['afternoon'] is True
    
    def test_student_attendance_report(self, setup_full_data):
        """Test detailed student attendance reporting"""
        data = setup_full_data
        service = AttendanceService(data['tenant'])
        student = data['students'][0]
        
        # Create attendance records over multiple days
        base_date = date.today() - timedelta(days=10)
        for i in range(10):
            current_date = base_date + timedelta(days=i)
            if current_date.weekday() < 5:  # Weekdays only
                # Create period entry first
                period_entry = PeriodEntry.objects.create(
                    month_date=current_date,
                    batch=data['batch'],
                    subject=data['subject'],
                    class_timing=data['class_timing'],
                    employee=data['employee'],
                    tenant=data['tenant']
                )
                
                Attendance.objects.create(
                    student=student,
                    period_table_entry=period_entry,
                    batch=data['batch'],
                    month_date=current_date,
                    forenoon=i % 3 != 0,  # 2/3 present forenoon
                    afternoon=i % 2 == 0,  # 1/2 present afternoon
                    reason='Test reason' if i % 4 == 0 else '',
                    tenant=data['tenant']
                )
        
        # Get student attendance report
        start_date = (base_date).strftime('%Y-%m-%d')
        end_date = (base_date + timedelta(days=9)).strftime('%Y-%m-%d')
        
        report = service.get_student_attendance_report(str(student.id), start_date, end_date)
        
        assert report['student'] == student
        assert report['total_days'] > 0  # Should have some weekdays
        assert 'present_days' in report
        assert 'absent_days' in report
        assert 'partial_days' in report
        assert 'attendance_percentage' in report
        assert len(report['attendance_records']) == report['total_days']
    
    def test_batch_attendance_report(self, setup_full_data):
        """Test batch-level attendance reporting"""
        data = setup_full_data
        service = AttendanceService(data['tenant'])
        
        # Create some attendance data
        # Use the most recent weekday so the service's school-day count is always 1.
        from datetime import timedelta
        target_date = date.today()
        while target_date.weekday() >= 5:
            target_date -= timedelta(days=1)
        period_entry = PeriodEntry.objects.create(
            month_date=target_date,
            batch=data['batch'],
            subject=data['subject'],
            class_timing=data['class_timing'],
            employee=data['employee'],
            tenant=data['tenant']
        )
        
        for i, student in enumerate(data['students'][:5]):  # Only first 5 students
            Attendance.objects.create(
                student=student,
                period_table_entry=period_entry,
                batch=data['batch'],
                month_date=target_date,
                forenoon=True,
                afternoon=i % 2 == 0,  # Alternating afternoon attendance
                tenant=data['tenant']
            )
        
        # Get batch report
        start_date = target_date.strftime('%Y-%m-%d')
        end_date = target_date.strftime('%Y-%m-%d')
        
        report = service.get_batch_attendance_report(str(data['batch'].id), start_date, end_date)
        
        assert report['batch'] == data['batch']
        assert report['total_students'] == 10
        assert len(report['student_summaries']) == 10
        assert report['total_days'] == 1
        assert 'average_attendance' in report
    
    def test_monthly_summaries(self, setup_full_data):
        """Test monthly summary functions"""
        data = setup_full_data
        service = AttendanceService(data['tenant'])
        student = data['students'][0]
        
        # Test student monthly summary
        current_month = date.today().strftime('%Y-%m')
        student_summary = service.get_student_monthly_summary(str(student.id), current_month)
        
        assert student_summary['student'] == student
        assert 'total_days' in student_summary
        assert 'attendance_percentage' in student_summary
        
        # Test batch monthly summary
        batch_summary = service.get_batch_monthly_summary(str(data['batch'].id), current_month)
        
        assert batch_summary['batch'] == data['batch']
        assert 'total_students' in batch_summary
        assert 'average_attendance' in batch_summary
    
    def test_daily_attendance_report(self, setup_full_data):
        """Test daily attendance reporting"""
        data = setup_full_data
        service = AttendanceService(data['tenant'])
        target_date = date.today()
        
        # Create attendance data for today
        period_entry = PeriodEntry.objects.create(
            month_date=target_date,
            batch=data['batch'],
            subject=data['subject'],
            class_timing=data['class_timing'],
            employee=data['employee'],
            tenant=data['tenant']
        )
        
        for i, student in enumerate(data['students']):
            Attendance.objects.create(
                student=student,
                period_table_entry=period_entry,
                batch=data['batch'],
                month_date=target_date,
                forenoon=i % 2 == 0,
                afternoon=i % 3 == 0,
                reason='Test' if i % 4 == 0 else '',
                tenant=data['tenant']
            )
        
        # Get daily report
        report = service.get_daily_attendance_report(str(data['batch'].id), target_date.strftime('%Y-%m-%d'))
        
        assert report['batch'] == data['batch']
        assert report['report_date'] == target_date
        assert report['total_students'] == 10
        assert len(report['student_attendance']) == 10
        assert 'present_count' in report
        assert 'absent_count' in report
        assert 'partial_count' in report
        assert 'attendance_percentage' in report
    
    def test_get_batch_students_for_attendance(self, setup_full_data):
        """Test getting students in batch for attendance interface"""
        data = setup_full_data
        service = AttendanceService(data['tenant'])
        target_date = date.today()
        
        # Create some existing attendance
        period_entry = PeriodEntry.objects.create(
            month_date=target_date,
            batch=data['batch'],
            subject=data['subject'],
            class_timing=data['class_timing'],
            employee=data['employee'],
            tenant=data['tenant']
        )
        
        # Create attendance for first student
        Attendance.objects.create(
            student=data['students'][0],
            period_table_entry=period_entry,
            batch=data['batch'],
            month_date=target_date,
            forenoon=False,
            afternoon=True,
            reason='Late',
            tenant=data['tenant']
        )
        
        students_data = service.get_batch_students_for_attendance(
            str(data['batch'].id),
            target_date.strftime('%Y-%m-%d')
        )
        
        assert len(students_data) == 10
        
        # First student should have existing attendance data
        first_student_data = students_data[0]
        assert first_student_data['forenoon'] is False
        assert first_student_data['afternoon'] is True
        assert first_student_data['reason'] == 'Late'
        
        # Other students should have defaults
        second_student_data = students_data[1]
        assert second_student_data['forenoon'] is True
        assert second_student_data['afternoon'] is True
        assert second_student_data['reason'] == ''
    
    def test_transaction_rollback_on_error(self, setup_full_data):
        """Test that database transactions are properly rolled back on errors"""
        data = setup_full_data
        service = AttendanceService(data['tenant'])
        student = data['students'][0]
        # (setup_full_data already enrolled every student via BatchStudent.)

        # Mock the logging service to raise an exception. record_student_attendance
        # logs via log_action, so patch that (the whole method is @transaction.atomic).
        with patch.object(service.logger, 'log_action', side_effect=Exception("Logging failed")):
            initial_count = Attendance.objects.count()
            
            with pytest.raises(Exception):
                service.record_student_attendance(
                    student_id=str(student.id),
                    batch_id=str(data['batch'].id),
                    attendance_date=_nearest_school_day(),
                    forenoon=True,
                    afternoon=True,
                )
            
            # Should not have created any attendance records due to transaction rollback
            final_count = Attendance.objects.count()
            assert final_count == initial_count
    
    def test_concurrent_attendance_updates(self, setup_full_data):
        """Test handling of concurrent attendance updates"""
        data = setup_full_data
        service = AttendanceService(data['tenant'])
        student = data['students'][0]
        # (setup_full_data already enrolled every student via BatchStudent.)

        attendance_date = _nearest_school_day()

        # Create initial attendance
        attendance1 = service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(data['batch'].id),
            attendance_date=attendance_date,
            forenoon=True,
            afternoon=True,
            reason="Initial"
        )

        # Simulate concurrent update (update_or_create on the same key)
        attendance2 = service.record_student_attendance(
            student_id=str(student.id),
            batch_id=str(data['batch'].id),
            attendance_date=attendance_date,
            forenoon=False,
            afternoon=False,
            reason="Updated"
        )

        # Should be the same record, updated
        assert attendance1.id == attendance2.id
        assert attendance2.forenoon is False
        assert attendance2.afternoon is False
        assert attendance2.reason == "Updated"

        # Should only have one record in database
        total_records = Attendance.objects.filter(
            student=student,
            batch=data['batch'],
            month_date=attendance_date
        ).count()
        assert total_records == 1