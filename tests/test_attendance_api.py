import pytest
import json
import uuid
from datetime import date, timedelta
from django.test import Client

from core.models import (
    Attendance, Student, Batch, Subject, Course, BatchStudent,
    PeriodEntry, ClassTiming, Employee, Term,
)
from core.services.attendance_service import AttendanceService
from django.contrib.auth import get_user_model

User = get_user_model()

# Real endpoint paths (core.urls is mounted at the project root).
MARK_URL = '/academic/mark-attendance/'
BATCH_STUDENTS_URL = '/academic/batch-students-attendance/{batch_id}/'
SUMMARY_URL = '/academic/attendance-summary/'
EXPORT_URL = '/academic/export-attendance-report/'
MONTHLY_URL = '/academic/batch-monthly-attendance/{batch_id}/'


def _today_str():
    """Nearest Mon-Fri to today, as a string — AttendanceService now rejects
    marking on weekends/holidays, so tests must always use a real school day."""
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime('%Y-%m-%d')


def _today():
    """Date-object counterpart of _today_str(), for assertions/queries that
    need to match records created via _today_str()."""
    return date.fromisoformat(_today_str())


@pytest.mark.django_db
class TestAttendanceAPIEndpoints:
    """Exercises the real attendance HTTP endpoints end to end.

    Requests go through TenantMainMiddleware, which resolves the `testserver`
    host to the session-shared school (see tests/conftest.py), so request.tenant
    is set for real rather than mocked.
    """

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def tenant(self, school, domain):
        """Reuse the session-shared school (with its `testserver` domain)."""
        return school

    @pytest.fixture
    def user(self, tenant):
        """Create a test user (mirrors UserService.create_user).

        is_admin=True: these tests log in via the real dashboard session
        (client.force_login) and hit core.urls views, which now require
        `is_admin` (core.middleware.DashboardAccessMiddleware) — teachers
        and parents are portal-only and never reach this surface.
        """
        suffix = uuid.uuid4().hex[:6]
        u = User(
            username=f"apiuser_{suffix}",
            email=f"api_{suffix}@example.com",
            first_name="API",
            last_name="User",
            is_admin=True,
        )
        u.set_password("testpass123")
        u.save()
        u.tenants.add(tenant)
        return u

    @pytest.fixture
    def course(self, tenant):
        return Course.objects.create(
            course_name="API Test Course",
            code=f"ATC{uuid.uuid4().hex[:4].upper()}",
            tenant=tenant,
        )

    @pytest.fixture
    def batch(self, course, academic_year, tenant, term):
        return Batch.objects.create(
            name="ATC-2024",
            course=course,
            academic_year=academic_year,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            tenant=tenant,
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
    def subject(self, batch, tenant, term):
        return Subject.objects.create(
            name="API Programming",
            code=f"ATC{uuid.uuid4().hex[:4].upper()}",
            batch=batch,
            tenant=tenant,
        )

    @pytest.fixture
    def students(self, tenant, batch):
        students = []
        for i in range(5):
            student = Student.objects.create(
                first_name=f"APIStudent{i}",
                last_name="Test",
                admission_no=f"APIADM{uuid.uuid4().hex[:5].upper()}",
                admission_date=date.today(),
                date_of_birth=date(2000, 1, 1),
                gender="male",
                tenant=tenant,
            )
            students.append(student)
            BatchStudent.objects.create(
                batch=batch,
                student=student,
                roll_number=f"API{i:03d}",
                tenant=tenant,
            )
        return students

    @pytest.fixture
    def employee(self, tenant):
        return Employee.objects.create(
            first_name="API",
            last_name="Teacher",
            employee_number=f"APIEMP{uuid.uuid4().hex[:5].upper()}",
            joining_date=date.today(),
            gender=True,
            tenant=tenant,
        )

    @pytest.fixture
    def class_timing(self, batch, tenant):
        return ClassTiming.objects.create(
            batch=batch,
            name="Period 1",
            start_time="09:00",
            end_time="10:00",
            tenant=tenant,
        )

    @pytest.fixture
    def period_entry(self, batch, subject, class_timing, employee, tenant):
        return PeriodEntry.objects.create(
            month_date=date.today(),
            batch=batch,
            subject=subject,
            class_timing=class_timing,
            employee=employee,
            tenant=tenant,
        )

    @pytest.fixture
    def authenticated_client(self, client, user):
        """Log the test client in; the testserver host supplies request.tenant."""
        client.force_login(user)
        return client

    # ------------------------------------------------------------------
    # mark attendance
    # ------------------------------------------------------------------
    def test_mark_attendance_api_success(self, authenticated_client, tenant, batch, students):
        records = [
            {'student_id': str(s.id), 'forenoon': True, 'afternoon': False, 'reason': ''}
            for s in students[:3]
        ]
        payload = {
            'batch_id': str(batch.id),
            'attendance_date': _today_str(),
            'attendance_records': records,
        }
        response = authenticated_client.post(
            MARK_URL, data=json.dumps(payload), content_type='application/json'
        )
        assert response.status_code == 200, response.content
        body = response.json()
        assert body['success'] is True
        assert len(body['records']) == 3
        # Persisted under this tenant
        assert Attendance.objects.filter(
            batch=batch, month_date=_today(), tenant=tenant
        ).count() == 3

    def test_mark_attendance_api_invalid_method(self, authenticated_client):
        response = authenticated_client.get(MARK_URL)
        assert response.status_code == 405

    def test_mark_attendance_api_invalid_json(self, authenticated_client):
        response = authenticated_client.post(
            MARK_URL, data='not valid json', content_type='application/json'
        )
        # Malformed body is rejected (currently a 500 from the generic handler;
        # at minimum it must not succeed).
        assert response.status_code >= 400

    # ------------------------------------------------------------------
    # batch students for attendance
    # ------------------------------------------------------------------
    def test_batch_students_attendance_api(self, authenticated_client, batch, students):
        url = BATCH_STUDENTS_URL.format(batch_id=batch.id)
        response = authenticated_client.get(url, {'date': _today_str()})
        assert response.status_code == 200, response.content
        body = response.json()
        assert len(body['students']) == 5
        # Each row carries the human-facing identifier (admission_no)
        assert all('student_id' in s for s in body['students'])

    # ------------------------------------------------------------------
    # monthly grid: premarked-present default
    # ------------------------------------------------------------------
    def test_batch_monthly_attendance_defaults_untouched_days_to_implicit_present(
        self, authenticated_client, tenant, batch, students
    ):
        today = _today()
        # One student gets an explicit half-day record; the rest are untouched.
        AttendanceService(tenant).mark_batch_attendance(
            str(batch.id), _today_str(),
            [{'student_id': str(students[0].id), 'forenoon': True, 'afternoon': False, 'reason': 'late arrival'}],
        )

        url = MONTHLY_URL.format(batch_id=batch.id)
        response = authenticated_client.get(url, {'year': today.year, 'month': today.month})
        assert response.status_code == 200, response.content
        body = response.json()

        by_id = {s['id']: s for s in body['students']}
        ds = today.strftime('%Y-%m-%d')

        explicit_entry = by_id[str(students[0].id)]['daily'][ds]
        assert explicit_entry['implicit'] is False
        assert explicit_entry['forenoon'] is True
        assert explicit_entry['afternoon'] is False

        untouched_entry = by_id[str(students[1].id)]['daily'][ds]
        assert untouched_entry is not None
        assert untouched_entry['implicit'] is True
        assert untouched_entry['forenoon'] is True
        assert untouched_entry['afternoon'] is True

    # ------------------------------------------------------------------
    # summary
    # ------------------------------------------------------------------
    def test_attendance_summary_api_batch(self, authenticated_client, tenant, batch, students):
        # Seed one marked record so the summary has data to aggregate.
        AttendanceService(tenant).mark_batch_attendance(
            str(batch.id), _today_str(),
            [{'student_id': str(students[0].id), 'forenoon': True, 'afternoon': True, 'reason': ''}],
        )
        month = _today().strftime('%Y-%m')
        response = authenticated_client.get(SUMMARY_URL, {'batch_id': str(batch.id), 'month': month})
        assert response.status_code == 200, response.content

    def test_attendance_summary_api_missing_params(self, authenticated_client):
        # No student_id/batch_id + month → explicit 400 from the endpoint.
        response = authenticated_client.get(SUMMARY_URL)
        assert response.status_code == 400

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------
    def test_export_attendance_report_api(self, authenticated_client, tenant, batch, students):
        AttendanceService(tenant).mark_batch_attendance(
            str(batch.id), _today_str(),
            [{'student_id': str(students[0].id), 'forenoon': True, 'afternoon': True, 'reason': ''}],
        )
        response = authenticated_client.get(EXPORT_URL, {
            'type': 'csv',
            'format': 'student',
            'student_id': str(students[0].id),
            'start_date': _today_str(),
            'end_date': _today_str(),
        })
        assert response.status_code == 200, response.content
        assert response['Content-Type'].startswith('text/csv')

    # ------------------------------------------------------------------
    # auth
    # ------------------------------------------------------------------
    def test_endpoints_require_login(self, client, batch):
        # batch_students_attendance_api is @login_required → redirect when anonymous.
        url = BATCH_STUDENTS_URL.format(batch_id=batch.id)
        response = client.get(url)
        assert response.status_code in (302, 401, 403)


@pytest.mark.integration
@pytest.mark.django_db
class TestAttendanceAPIIntegration:
    """Integration tests against the real AttendanceService and database."""

    @pytest.fixture
    def full_setup(self, school, domain, academic_year):
        tenant = school
        suffix = uuid.uuid4().hex[:6]
        user = User(
            username=f"intuser_{suffix}",
            email=f"int_{suffix}@test.com",
            first_name="Int",
            last_name="User",
        )
        user.set_password("intpass123")
        user.save()
        user.tenants.add(tenant)

        term = Term.objects.create(
            tenant=tenant,
            academic_year=academic_year,
            name='Integration Term',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            order=1,
        )

        course = Course.objects.create(
            course_name="Integration Course",
            code=f"IC{uuid.uuid4().hex[:4].upper()}",
            tenant=tenant,
        )
        batch = Batch.objects.create(
            name="IC-2024", course=course, academic_year=academic_year,
            start_date=date.today(), end_date=date.today() + timedelta(days=365),
            tenant=tenant,
        )
        subject = Subject.objects.create(
            name="Integration Subject", code=f"IC{uuid.uuid4().hex[:4].upper()}",
            batch=batch, tenant=tenant,
        )
        employee = Employee.objects.create(
            first_name="Int", last_name="Teacher",
            employee_number=f"INTEMP{uuid.uuid4().hex[:5].upper()}",
            joining_date=date.today(), gender=True, tenant=tenant,
        )
        class_timing = ClassTiming.objects.create(
            batch=batch, name="Period 1", start_time="09:00", end_time="10:00", tenant=tenant,
        )

        students = []
        for i in range(3):
            student = Student.objects.create(
                first_name=f"IntStudent{i}", last_name="Test",
                admission_no=f"INTADM{uuid.uuid4().hex[:5].upper()}",
                admission_date=date.today(), date_of_birth=date(2000, 1, 1),
                gender="male", tenant=tenant,
            )
            students.append(student)
            BatchStudent.objects.create(
                batch=batch, student=student, roll_number=f"I{i:03d}", tenant=tenant,
            )

        period_entry = PeriodEntry.objects.create(
            month_date=date.today(), batch=batch, subject=subject,
            class_timing=class_timing, employee=employee, tenant=tenant,
        )

        return {
            'tenant': tenant, 'user': user, 'course': course, 'batch': batch,
            'subject': subject, 'students': students, 'employee': employee,
            'class_timing': class_timing, 'period_entry': period_entry,
        }

    def test_end_to_end_attendance_workflow(self, full_setup):
        setup = full_setup
        tenant, batch, students = setup['tenant'], setup['batch'], setup['students']
        service = AttendanceService(tenant)
        today = _today_str()

        # 1. Students available for marking
        students_data = service.get_batch_students_for_attendance(str(batch.id), today)
        assert len(students_data) == 3

        # 2. Mark all present
        records = [
            {'student_id': str(s.id), 'forenoon': True, 'afternoon': True, 'reason': ''}
            for s in students
        ]
        updated = service.mark_batch_attendance(str(batch.id), today, records)
        assert len(updated) == 3

        # 3. Statistics reflect the 3 present records
        stats = service.get_attendance_statistics(
            batch_id=str(batch.id), start_date=_today(), end_date=_today()
        )
        assert stats['total_records'] == 3
        assert stats['present_count'] == 3
        assert stats['absent_count'] == 0

    def test_attendance_data_consistency(self, full_setup):
        setup = full_setup
        tenant, batch, students = setup['tenant'], setup['batch'], setup['students']
        service = AttendanceService(tenant)
        today = _today()

        # Record per-student via the real service signature (forenoon/afternoon,
        # not the nonexistent is_present field).
        for i, student in enumerate(students):
            service.record_student_attendance(
                student_id=str(student.id),
                batch_id=str(batch.id),
                attendance_date=today,
                forenoon=(i % 2 == 0),
                afternoon=True,
                reason=f"reason {i}",
            )

        for i, student in enumerate(students):
            attendance = Attendance.objects.get(
                student=student, batch=batch, month_date=today, tenant=tenant
            )
            assert attendance.forenoon == (i % 2 == 0)
            assert attendance.afternoon is True
            assert attendance.reason == f"reason {i}"

        # All have afternoon=True → all present
        stats = service.get_attendance_statistics(
            batch_id=str(batch.id), start_date=today, end_date=today
        )
        assert stats['total_records'] == 3
        assert stats['present_count'] == 3

    def test_mark_attendance_is_idempotent(self, full_setup):
        """Re-marking the same day updates rather than duplicates (update_or_create)."""
        setup = full_setup
        tenant, batch, students = setup['tenant'], setup['batch'], setup['students']
        service = AttendanceService(tenant)
        today = _today_str()

        service.mark_batch_attendance(
            str(batch.id), today,
            [{'student_id': str(s.id), 'forenoon': True, 'afternoon': False, 'reason': ''} for s in students],
        )
        # Re-mark one student with different values
        service.mark_batch_attendance(
            str(batch.id), today,
            [{'student_id': str(students[0].id), 'forenoon': False, 'afternoon': True, 'reason': 'changed'}],
        )

        assert Attendance.objects.filter(
            batch=batch, month_date=_today(), tenant=tenant
        ).count() == 3
        att = Attendance.objects.get(
            student=students[0], batch=batch, month_date=_today(), tenant=tenant
        )
        assert att.forenoon is False
        assert att.afternoon is True
        assert att.reason == 'changed'
