import json
import uuid
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core.models import (
    AcademicYear,
    AttendanceSettings,
    Attendance,
    Batch,
    BatchStudent,
    Course,
    Employee,
    Event,
    Student,
)

User = get_user_model()

REGISTER_URL = '/api/portal/teacher/classes/{batch_id}/register/'


def _school_day():
    """Nearest Mon-Fri to today, as a date -- a safe default "open" school day."""
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _saturday():
    """Nearest Saturday to today -- never a school day under the default settings."""
    d = date.today()
    while d.weekday() != 5:
        d -= timedelta(days=1)
    return d


@pytest.mark.django_db
class TestPortalAttendanceRegister:
    """Exercises the teacher portal's attendance register endpoint end to end,
    mirroring tests/test_attendance_api.py's fixtures for the admin surface.
    """

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def tenant(self, school, domain):
        return school

    @pytest.fixture
    def course(self, tenant):
        return Course.objects.create(
            course_name="Portal Test Course",
            code=f"PTC{uuid.uuid4().hex[:4].upper()}",
            tenant=tenant,
        )

    @pytest.fixture
    def batch(self, course, academic_year, tenant, term):
        return Batch.objects.create(
            name="PTC-2024",
            course=course,
            academic_year=academic_year,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            tenant=tenant,
        )

    @pytest.fixture
    def term(self, tenant, academic_year):
        """Term covering today's date (required for attendance marking gate)."""
        from datetime import timedelta
        from core.models import Term
        return Term.objects.create(
            tenant=tenant,
            academic_year=academic_year,
            name='Test Term',
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            order=1,
        )

    @pytest.fixture
    def students(self, tenant, batch, term):
        students = []
        for i in range(3):
            student = Student.objects.create(
                first_name=f"PortalStudent{i}",
                last_name="Test",
                admission_no=f"PTADM{uuid.uuid4().hex[:5].upper()}",
                admission_date=date.today(),
                date_of_birth=date(2000, 1, 1),
                gender="male",
                tenant=tenant,
            )
            students.append(student)
            BatchStudent.objects.create(
                batch=batch,
                student=student,
                roll_number=f"PT{i:03d}",
                tenant=tenant,
            )
        return students

    @pytest.fixture
    def class_teacher_user(self, tenant, batch):
        """A teacher who IS the class teacher for `batch`."""
        suffix = uuid.uuid4().hex[:6]
        user = User(
            username=f"classteacher_{suffix}",
            email=f"classteacher_{suffix}@example.com",
            first_name="Class",
            last_name="Teacher",
        )
        user.set_password("testpass123")
        user.save()
        user.tenants.add(tenant)

        employee = Employee.objects.create(
            first_name="Class",
            last_name="Teacher",
            employee_number=f"PTEMP{uuid.uuid4().hex[:5].upper()}",
            joining_date=date.today(),
            gender=True,
            tenant=tenant,
            user=user,
        )
        batch.class_teachers.add(employee)
        return user

    @pytest.fixture
    def subject_teacher_user(self, tenant):
        """A teacher who is NOT the class teacher for `batch` (no batch link)."""
        suffix = uuid.uuid4().hex[:6]
        user = User(
            username=f"subjectteacher_{suffix}",
            email=f"subjectteacher_{suffix}@example.com",
            first_name="Subject",
            last_name="Teacher",
        )
        user.set_password("testpass123")
        user.save()
        user.tenants.add(tenant)

        Employee.objects.create(
            first_name="Subject",
            last_name="Teacher",
            employee_number=f"PTEMP{uuid.uuid4().hex[:5].upper()}",
            joining_date=date.today(),
            gender=True,
            tenant=tenant,
            user=user,
        )
        return user

    @pytest.fixture
    def class_teacher_client(self, client, class_teacher_user):
        client.force_login(class_teacher_user)
        return client

    # ------------------------------------------------------------------
    # GET: premarked-present default
    # ------------------------------------------------------------------
    def test_get_defaults_to_present_with_no_record(self, class_teacher_client, batch, students):
        url = REGISTER_URL.format(batch_id=batch.id)
        response = class_teacher_client.get(url, {'date': _school_day().isoformat()})
        assert response.status_code == 200, response.content
        body = response.json()
        assert len(body['entries']) == 3
        assert all(entry['status'] == 'present' for entry in body['entries'])

    def test_get_non_class_teacher_is_404(self, client, subject_teacher_user, batch, students):
        client.force_login(subject_teacher_user)
        url = REGISTER_URL.format(batch_id=batch.id)
        response = client.get(url, {'date': _school_day().isoformat()})
        assert response.status_code == 404

    # ------------------------------------------------------------------
    # POST: school-day / holiday validation (new behavior)
    # ------------------------------------------------------------------
    def test_post_on_weekend_is_rejected(self, class_teacher_client, batch, students):
        url = REGISTER_URL.format(batch_id=batch.id)
        payload = {
            'date': _saturday().isoformat(),
            'entries': [
                {'student_id': str(students[0].id), 'status': 'present', 'reason': ''},
            ],
        }
        response = class_teacher_client.post(
            url, data=json.dumps(payload), content_type='application/json'
        )
        assert response.status_code == 400, response.content
        assert not Attendance.objects.filter(
            student=students[0], batch=batch, month_date=_saturday()
        ).exists()

    def test_post_on_holiday_is_rejected(self, class_teacher_client, tenant, batch, students, academic_year):
        holiday_date = _school_day()
        Event.objects.create(
            tenant=tenant,
            academic_year=academic_year,
            title="Test Holiday",
            start_date=f"{holiday_date} 00:00:00",
            end_date=f"{holiday_date} 23:59:59",
            is_holiday=True,
        )
        url = REGISTER_URL.format(batch_id=batch.id)
        payload = {
            'date': holiday_date.isoformat(),
            'entries': [
                {'student_id': str(students[0].id), 'status': 'present', 'reason': ''},
            ],
        }
        response = class_teacher_client.post(
            url, data=json.dumps(payload), content_type='application/json'
        )
        assert response.status_code == 400, response.content

    # ------------------------------------------------------------------
    # POST: lock-window enforcement (new behavior) -- teachers never bypass,
    # even when the tenant allows admins to unlock.
    # ------------------------------------------------------------------
    def test_post_on_locked_date_is_rejected(self, class_teacher_client, tenant, batch, students):
        settings = AttendanceSettings.get_settings(tenant)
        settings.mark_frequency = 'lock'
        settings.lock_after_days = 7
        settings.allow_admin_unlock = True  # even so, teachers must not bypass
        settings.save()

        locked_date = _school_day() - timedelta(days=10)
        while locked_date.weekday() >= 5:
            locked_date -= timedelta(days=1)

        url = REGISTER_URL.format(batch_id=batch.id)
        payload = {
            'date': locked_date.isoformat(),
            'entries': [
                {'student_id': str(students[0].id), 'status': 'present', 'reason': ''},
            ],
        }
        response = class_teacher_client.post(
            url, data=json.dumps(payload), content_type='application/json'
        )
        assert response.status_code == 400, response.content

    # ------------------------------------------------------------------
    # POST: success + idempotency on a valid, open school day (regression guard)
    # ------------------------------------------------------------------
    def test_post_succeeds_and_is_idempotent_on_open_day(self, class_teacher_client, tenant, batch, students):
        url = REGISTER_URL.format(batch_id=batch.id)
        day = _school_day()
        payload = {
            'date': day.isoformat(),
            'entries': [
                {'student_id': str(s.id), 'status': 'present', 'reason': ''} for s in students
            ],
        }
        response = class_teacher_client.post(
            url, data=json.dumps(payload), content_type='application/json'
        )
        assert response.status_code == 200, response.content
        assert response.json()['saved'] == 3
        assert Attendance.objects.filter(batch=batch, month_date=day, tenant=tenant).count() == 3

        # Re-save one student as absent -- should update, not duplicate.
        payload2 = {
            'date': day.isoformat(),
            'entries': [
                {'student_id': str(students[0].id), 'status': 'absent', 'reason': 'sick'},
            ],
        }
        response2 = class_teacher_client.post(
            url, data=json.dumps(payload2), content_type='application/json'
        )
        assert response2.status_code == 200, response2.content
        assert Attendance.objects.filter(batch=batch, month_date=day, tenant=tenant).count() == 3
        record = Attendance.objects.get(student=students[0], batch=batch, month_date=day, tenant=tenant)
        assert record.forenoon is False
        assert record.afternoon is False
        assert record.reason == 'sick'

    def test_post_non_class_teacher_is_404(self, client, subject_teacher_user, batch, students):
        client.force_login(subject_teacher_user)
        url = REGISTER_URL.format(batch_id=batch.id)
        payload = {
            'date': _school_day().isoformat(),
            'entries': [
                {'student_id': str(students[0].id), 'status': 'present', 'reason': ''},
            ],
        }
        response = client.post(url, data=json.dumps(payload), content_type='application/json')
        assert response.status_code == 404
