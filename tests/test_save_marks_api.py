"""Tests for save_marks_api — regression coverage for the "Grades saved
successfully but nothing was saved" bug: Grade 1/2 (grade-only, LEVEL/LETTER
scale) exams were silently losing rows because the endpoint always returned
`success: True` even when every per-student save failed, and a stale/foreign
`grade_value_id` would 404 without surfacing to the caller.
"""

import uuid
from datetime import date, timedelta, datetime

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from core.models import (
    Batch,
    Course,
    Exam,
    ExamGroup,
    ExamScore,
    GradeValue,
    GradingScale,
    Student,
    BatchStudent,
    Subject,
)
from portal.models import MarkSubmission

User = get_user_model()

SAVE_URL = '/api/marks/save/'


@pytest.fixture
def tenant(school, domain):
    return school


@pytest.fixture
def admin_client(tenant):
    suffix = uuid.uuid4().hex[:6]
    u = User(
        username=f"marksadmin_{suffix}",
        email=f"marksadmin_{suffix}@example.com",
        first_name="Marks", last_name="Admin", is_admin=True,
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(tenant)
    c = Client()
    c.force_login(u)
    c.user = u
    return c


def _grading_scale(tenant, scale_type='LETTER'):
    return GradingScale.objects.create(
        tenant=tenant,
        name=f"Scale {uuid.uuid4().hex[:4]}",
        code=f"SCALE-{uuid.uuid4().hex[:6].upper()}",
        scale_type=scale_type,
    )


def _grade_value(scale, tenant, name='A'):
    return GradeValue.objects.create(
        tenant=tenant, grading_scale=scale, name=name,
        code=name, display_order=1,
    )


def _exam_group(batch, tenant, published=True):
    return ExamGroup.objects.create(
        tenant=tenant, name=f"Plan {uuid.uuid4().hex[:4]}", batch=batch,
        exam_type="TERM", exam_date=date.today(), is_published=published,
    )


def _students(batch, tenant, count):
    out = []
    for i in range(count):
        s = Student.objects.create(
            tenant=tenant, first_name=f"S{i}", last_name="Test",
            admission_no=f"ADM{uuid.uuid4().hex[:6].upper()}",
            admission_date=date.today(), date_of_birth=date(2018, 1, 1),
            gender="male",
        )
        BatchStudent.objects.create(
            tenant=tenant, batch=batch, student=s,
            roll_number=f"R{uuid.uuid4().hex[:3].upper()}",
        )
        out.append(s)
    return out


def _grade_only_exam(batch, subject, tenant, scale):
    eg = _exam_group(batch, tenant)
    return Exam.objects.create(
        tenant=tenant, exam_group=eg, subject=subject,
        start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1),
        maximum_marks=0, minimum_marks=0, grading_scale=scale,
        assessment_slot='CLASSWORK',
    )


def _numeric_exam(batch, subject, tenant):
    eg = _exam_group(batch, tenant)
    return Exam.objects.create(
        tenant=tenant, exam_group=eg, subject=subject,
        start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1),
        maximum_marks=100, minimum_marks=0,
        assessment_slot='EXAM',
    )


@pytest.mark.django_db
@pytest.mark.integration
class TestSaveMarksApi:

    def test_happy_path_numeric(self, admin_client, tenant, batch, subject):
        exam = _numeric_exam(batch, subject, tenant)
        students = _students(batch, tenant, 3)
        marks = [
            {'student_id': str(s.id), 'marks': 80 + i, 'is_absent': False}
            for i, s in enumerate(students)
        ]
        resp = admin_client.post(SAVE_URL, {'exam_id': str(exam.id), 'marks': marks},
                                  content_type='application/json')
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data['success'] is True
        assert data['attempted_count'] == 3
        assert data['saved_count'] == 3
        assert data['failed_count'] == 0
        assert data['errors'] == []
        assert ExamScore.objects.filter(exam=exam).count() == 3

    def test_happy_path_grades(self, admin_client, tenant, batch, subject):
        scale = _grading_scale(tenant, scale_type='LETTER')
        gv = _grade_value(scale, tenant, name='A')
        exam = _grade_only_exam(batch, subject, tenant, scale)
        students = _students(batch, tenant, 2)
        marks = [
            {'student_id': str(s.id), 'grade_value_id': str(gv.id), 'is_absent': False}
            for s in students
        ]
        resp = admin_client.post(SAVE_URL, {'exam_id': str(exam.id), 'marks': marks},
                                  content_type='application/json')
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data['success'] is True
        assert data['saved_count'] == 2
        assert data['failed_count'] == 0
        assert ExamScore.objects.filter(exam=exam, grade_value=gv).count() == 2

    def test_stale_grade_value_id_reported_as_failure_not_success(
        self, admin_client, tenant, batch, subject,
    ):
        """Reproduces the reported bug: a grade_value_id that no longer
        resolves (e.g. deleted mid-day) must NOT produce success:True."""
        scale = _grading_scale(tenant, scale_type='LETTER')
        exam = _grade_only_exam(batch, subject, tenant, scale)
        students = _students(batch, tenant, 1)
        bogus_id = str(uuid.uuid4())
        marks = [{'student_id': str(students[0].id), 'grade_value_id': bogus_id, 'is_absent': False}]

        resp = admin_client.post(SAVE_URL, {'exam_id': str(exam.id), 'marks': marks},
                                  content_type='application/json')
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data['success'] is False
        assert data['attempted_count'] == 1
        assert data['saved_count'] == 0
        assert data['failed_count'] == 1
        assert any(students[0].full_name in e or 'Invalid grade' in e for e in data['errors'])
        assert not ExamScore.objects.filter(exam=exam).exists()

    def test_grade_value_from_other_scale_rejected(self, admin_client, tenant, batch, subject):
        """A grade_value_id that exists for the tenant but belongs to a
        different scale than this exam's must be rejected, not silently
        accepted (the old lookup only scoped by tenant, not by scale)."""
        scale = _grading_scale(tenant, scale_type='LETTER')
        other_scale = _grading_scale(tenant, scale_type='DESCRIPTIVE')
        foreign_gv = _grade_value(other_scale, tenant, name='Very Good')
        exam = _grade_only_exam(batch, subject, tenant, scale)
        students = _students(batch, tenant, 1)
        marks = [{'student_id': str(students[0].id), 'grade_value_id': str(foreign_gv.id), 'is_absent': False}]

        resp = admin_client.post(SAVE_URL, {'exam_id': str(exam.id), 'marks': marks},
                                  content_type='application/json')
        data = resp.json()
        assert data['success'] is False
        assert data['failed_count'] == 1
        assert not ExamScore.objects.filter(exam=exam).exists()

    def test_mixed_batch_partial_save_reports_accurately(self, admin_client, tenant, batch, subject):
        """One bad row must not block the rest of the class, and the
        response must accurately reflect a partial save (not blanket
        success, and not a full rollback)."""
        scale = _grading_scale(tenant, scale_type='LETTER')
        gv = _grade_value(scale, tenant, name='A')
        exam = _grade_only_exam(batch, subject, tenant, scale)
        good_students = _students(batch, tenant, 2)
        bad_student = _students(batch, tenant, 1)[0]

        marks = [
            {'student_id': str(s.id), 'grade_value_id': str(gv.id), 'is_absent': False}
            for s in good_students
        ] + [
            {'student_id': str(bad_student.id), 'grade_value_id': str(uuid.uuid4()), 'is_absent': False}
        ]

        resp = admin_client.post(SAVE_URL, {'exam_id': str(exam.id), 'marks': marks},
                                  content_type='application/json')
        data = resp.json()
        assert data['success'] is False
        assert data['attempted_count'] == 3
        assert data['saved_count'] == 2
        assert data['failed_count'] == 1
        assert ExamScore.objects.filter(exam=exam).count() == 2, (
            "the 2 valid rows must remain committed — this endpoint is "
            "best-effort per-row, not all-or-nothing"
        )
        assert not ExamScore.objects.filter(exam=exam, student=bad_student).exists()

    def test_full_success_flips_draft_submission_to_submitted(
        self, admin_client, tenant, batch, subject,
    ):
        """Regression for the exam-list status badge getting stuck on
        'Awaiting Submission': staff completing a save via this endpoint
        must flip an existing draft MarkSubmission (e.g. left behind by a
        teacher's portal draft-save) to submitted, not leave it stranded."""
        scale = _grading_scale(tenant, scale_type='LETTER')
        gv = _grade_value(scale, tenant, name='A')
        exam = _grade_only_exam(batch, subject, tenant, scale)
        students = _students(batch, tenant, 2)
        submission = MarkSubmission.objects.create(
            tenant=tenant, exam=exam, status=MarkSubmission.STATUS_DRAFT,
        )

        marks = [
            {'student_id': str(s.id), 'grade_value_id': str(gv.id), 'is_absent': False}
            for s in students
        ]
        resp = admin_client.post(SAVE_URL, {'exam_id': str(exam.id), 'marks': marks},
                                  content_type='application/json')
        assert resp.status_code == 200, resp.content
        assert resp.json()['success'] is True

        submission.refresh_from_db()
        assert submission.status == MarkSubmission.STATUS_SUBMITTED
        assert submission.submitted_by_id == admin_client.user.id
        assert submission.submitted_at is not None

    def test_partial_failure_leaves_submission_status_untouched(
        self, admin_client, tenant, batch, subject,
    ):
        """A save that isn't fully successful must never report/imply
        submission — an existing draft stays draft, and no MarkSubmission
        row is created at all when none existed beforehand."""
        scale = _grading_scale(tenant, scale_type='LETTER')
        gv = _grade_value(scale, tenant, name='A')
        exam = _grade_only_exam(batch, subject, tenant, scale)
        good_student = _students(batch, tenant, 1)[0]
        bad_student = _students(batch, tenant, 1)[0]
        submission = MarkSubmission.objects.create(
            tenant=tenant, exam=exam, status=MarkSubmission.STATUS_DRAFT,
        )

        marks = [
            {'student_id': str(good_student.id), 'grade_value_id': str(gv.id), 'is_absent': False},
            {'student_id': str(bad_student.id), 'grade_value_id': str(uuid.uuid4()), 'is_absent': False},
        ]
        resp = admin_client.post(SAVE_URL, {'exam_id': str(exam.id), 'marks': marks},
                                  content_type='application/json')
        assert resp.status_code == 200, resp.content
        assert resp.json()['success'] is False

        submission.refresh_from_db()
        assert submission.status == MarkSubmission.STATUS_DRAFT
        assert submission.submitted_at is None

        # No pre-existing MarkSubmission for a different exam: a failing
        # save must not create one either.
        other_exam = _grade_only_exam(batch, subject, tenant, scale)
        bad_marks = [{'student_id': str(good_student.id), 'grade_value_id': str(uuid.uuid4()), 'is_absent': False}]
        admin_client.post(SAVE_URL, {'exam_id': str(other_exam.id), 'marks': bad_marks},
                           content_type='application/json')
        assert not MarkSubmission.objects.filter(exam=other_exam).exists()
