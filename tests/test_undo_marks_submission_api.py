"""Tests for undo_marks_submission_api — the admin action that reopens a
subject's submitted marks for editing by flipping its MarkSubmission back to
draft, and (when the exam group's results were already published) also
unpublishes the exam group so stale report cards aren't left looking current.
"""

import uuid
from datetime import date, timedelta

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
    Term,
)
from portal.models import MarkSubmission, SkillsSubmission

User = get_user_model()


def undo_url(exam_id):
    return f'/api/gradebook/exam/{exam_id}/undo-submission/'


@pytest.fixture
def tenant(school, domain):
    return school


@pytest.fixture
def admin_client(tenant):
    suffix = uuid.uuid4().hex[:6]
    u = User(
        username=f"undoadmin_{suffix}",
        email=f"undoadmin_{suffix}@example.com",
        first_name="Undo", last_name="Admin", is_admin=True,
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(tenant)
    c = Client()
    c.force_login(u)
    c.user = u
    return c


def _exam_group(batch, tenant, result_published=False):
    return ExamGroup.objects.create(
        tenant=tenant, name=f"Plan {uuid.uuid4().hex[:4]}", batch=batch,
        exam_type="TERM", exam_date=date.today(), is_published=True,
        result_published=result_published,
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


def _numeric_exam(batch, subject, tenant, result_published=False):
    eg = _exam_group(batch, tenant, result_published=result_published)
    return Exam.objects.create(
        tenant=tenant, exam_group=eg, subject=subject,
        start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1),
        maximum_marks=100, minimum_marks=0,
        assessment_slot='EXAM',
    )


@pytest.mark.django_db
@pytest.mark.integration
class TestUndoMarksSubmissionApi:

    def test_undo_flips_submitted_to_draft_and_keeps_scores(self, admin_client, tenant, batch, subject):
        exam = _numeric_exam(batch, subject, tenant)
        student = _students(batch, tenant, 1)[0]
        ExamScore.objects.create(tenant=tenant, exam=exam, student=student, marks=90)
        submission = MarkSubmission.objects.create(
            tenant=tenant, exam=exam, status=MarkSubmission.STATUS_SUBMITTED,
            submitted_by=admin_client.user, submitted_at=timezone.now(),
        )

        resp = admin_client.post(undo_url(exam.id))
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data['success'] is True
        assert data['was_published'] is False

        submission.refresh_from_db()
        assert submission.status == MarkSubmission.STATUS_DRAFT
        assert submission.submitted_by is None
        assert submission.submitted_at is None
        assert ExamScore.objects.filter(exam=exam, student=student, marks=90).exists()

    def test_undo_also_unpublishes_exam_group_when_already_published(self, admin_client, tenant, batch, subject):
        exam = _numeric_exam(batch, subject, tenant, result_published=True)
        MarkSubmission.objects.create(
            tenant=tenant, exam=exam, status=MarkSubmission.STATUS_SUBMITTED,
            submitted_by=admin_client.user, submitted_at=timezone.now(),
        )

        resp = admin_client.post(undo_url(exam.id))
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data['success'] is True
        assert data['was_published'] is True

        exam.exam_group.refresh_from_db()
        assert exam.exam_group.result_published is False

    def test_undo_leaves_unpublished_exam_group_unpublished(self, admin_client, tenant, batch, subject):
        exam = _numeric_exam(batch, subject, tenant, result_published=False)
        MarkSubmission.objects.create(
            tenant=tenant, exam=exam, status=MarkSubmission.STATUS_SUBMITTED,
            submitted_by=admin_client.user, submitted_at=timezone.now(),
        )

        resp = admin_client.post(undo_url(exam.id))
        data = resp.json()
        assert data['success'] is True
        assert data['was_published'] is False
        exam.exam_group.refresh_from_db()
        assert exam.exam_group.result_published is False

    def test_undo_no_submission_row_is_a_no_op(self, admin_client, tenant, batch, subject):
        exam = _numeric_exam(batch, subject, tenant)

        resp = admin_client.post(undo_url(exam.id))
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data['success'] is False
        assert 'error' in data
        assert not MarkSubmission.objects.filter(exam=exam).exists()

    def test_undo_already_draft_submission_is_a_no_op(self, admin_client, tenant, batch, subject):
        exam = _numeric_exam(batch, subject, tenant)
        submission = MarkSubmission.objects.create(
            tenant=tenant, exam=exam, status=MarkSubmission.STATUS_DRAFT,
        )

        resp = admin_client.post(undo_url(exam.id))
        data = resp.json()
        assert data['success'] is False

        submission.refresh_from_db()
        assert submission.status == MarkSubmission.STATUS_DRAFT

    def test_undo_nonexistent_exam_reports_error(self, admin_client, tenant):
        """Matches the existing sibling endpoints (e.g. delete_exam_api,
        save_marks_api): the whole view body is wrapped in a blanket
        try/except, so Http404 from get_object_or_404 is caught and reported
        as a 200 JSON error rather than surfacing as an actual 404 response."""
        resp = admin_client.post(undo_url(uuid.uuid4()))
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data['success'] is False
        assert 'error' in data


def _pregrade_batch(tenant, academic_year, course_name="Reception"):
    course = Course.objects.create(
        tenant=tenant, course_name=course_name, code=f"C{uuid.uuid4().hex[:6].upper()}",
    )
    return Batch.objects.create(
        tenant=tenant, name=f"BATCH-{uuid.uuid4().hex[:6].upper()}", course=course,
        academic_year=academic_year, start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
    )


def _skills_exam(tenant, batch, term):
    subject = Subject.objects.create(
        tenant=tenant, code=f"S{uuid.uuid4().hex[:4].upper()}", name="Numeracy", batch=batch,
    )
    eg = ExamGroup.objects.create(
        tenant=tenant, name=f"Plan {uuid.uuid4().hex[:4]}", batch=batch,
        exam_type="TERM", exam_date=date.today(), is_published=True,
    )
    # Phase 3+: Terms are year-scoped, not per-batch. Use academic_year directly.
    Term.objects.create(
        tenant=tenant, academic_year=batch.academic_year, name=term,
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=30), order=1,
    )
    return Exam.objects.create(
        tenant=tenant, exam_group=eg, subject=subject,
        start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1),
        maximum_marks=100, minimum_marks=0, assessment_slot='EXAM',
    )


@pytest.mark.django_db
@pytest.mark.integration
class TestUndoSkillsSubmission:
    """Pre-grade (Reception/Nursery/...) exams never get a MarkSubmission row
    — their submission lives in the portal's SkillsSubmission (keyed by
    batch+term) instead. undo_marks_submission_api must reopen that instead
    of reporting "not submitted" just because no MarkSubmission exists."""

    def test_undo_reopens_submitted_skills_submission(self, admin_client, tenant, academic_year):
        GradingScale.objects.create(
            tenant=tenant, name="Skill Levels", code="SKILL_LEVELS",
            scale_type="LEVEL", is_active=True,
        )
        batch = _pregrade_batch(tenant, academic_year)
        exam = _skills_exam(tenant, batch, term="Term 1")
        term = Term.objects.get(tenant=tenant, academic_year=academic_year, name="Term 1")
        submission = SkillsSubmission.objects.create(
            tenant=tenant, batch=batch, term=term,
            status=SkillsSubmission.STATUS_SUBMITTED,
            submitted_by=admin_client.user, submitted_at=timezone.now(),
        )

        resp = admin_client.post(undo_url(exam.id))
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data['success'] is True

        submission.refresh_from_db()
        assert submission.status == SkillsSubmission.STATUS_DRAFT
        assert submission.submitted_by is None
        assert submission.submitted_at is None
        assert not MarkSubmission.objects.filter(exam=exam).exists()

    def test_undo_no_skills_submission_is_a_no_op(self, admin_client, tenant, academic_year):
        GradingScale.objects.create(
            tenant=tenant, name="Skill Levels", code="SKILL_LEVELS",
            scale_type="LEVEL", is_active=True,
        )
        batch = _pregrade_batch(tenant, academic_year)
        exam = _skills_exam(tenant, batch, term="Term 1")

        resp = admin_client.post(undo_url(exam.id))
        data = resp.json()
        assert data['success'] is False
        assert 'error' in data

    def test_undo_draft_skills_submission_is_a_no_op(self, admin_client, tenant, academic_year):
        GradingScale.objects.create(
            tenant=tenant, name="Skill Levels", code="SKILL_LEVELS",
            scale_type="LEVEL", is_active=True,
        )
        batch = _pregrade_batch(tenant, academic_year)
        exam = _skills_exam(tenant, batch, term="Term 1")
        term = Term.objects.get(tenant=tenant, academic_year=academic_year, name="Term 1")
        submission = SkillsSubmission.objects.create(
            tenant=tenant, batch=batch, term=term,
            status=SkillsSubmission.STATUS_DRAFT,
        )

        resp = admin_client.post(undo_url(exam.id))
        data = resp.json()
        assert data['success'] is False

        submission.refresh_from_db()
        assert submission.status == SkillsSubmission.STATUS_DRAFT


def _ordinary_batch(tenant, academic_year):
    course = Course.objects.create(
        tenant=tenant, course_name="Test Course", code=f"C{uuid.uuid4().hex[:6].upper()}",
    )
    return Batch.objects.create(
        tenant=tenant, name=f"BATCH-{uuid.uuid4().hex[:6].upper()}", course=course,
        academic_year=academic_year, start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
    )


def _grade_only_exam_no_scale(tenant, batch, exam_group, name):
    subject = Subject.objects.create(
        tenant=tenant, code=f"S{uuid.uuid4().hex[:4].upper()}", name=name, batch=batch,
    )
    return Exam.objects.create(
        tenant=tenant, exam_group=exam_group, subject=subject,
        start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1),
        maximum_marks=0, minimum_marks=0, assessment_slot='EXAM',
    )


@pytest.mark.django_db
@pytest.mark.integration
class TestUndoInferredSubmission:
    """Some exams (activity-planner-created rows, or scores entered directly
    via Django admin) never get a MarkSubmission or SkillsSubmission row at
    all, yet the badge still infers "Submitted" once every student has a
    score. undo_marks_submission_api must handle that case too, by creating
    a draft MarkSubmission rather than reporting "not submitted" — there's
    no real assessment_slot='EXAM'."""

    def test_undo_creates_draft_mark_submission_when_all_students_scored(self, admin_client, tenant, academic_year):
        batch = _ordinary_batch(tenant, academic_year)
        eg = ExamGroup.objects.create(
            tenant=tenant, name=f"Plan {uuid.uuid4().hex[:4]}", batch=batch,
            exam_type="TERM", exam_date=date.today(), is_published=True,
        )
        students = _students(batch, tenant, 2)
        exam = _grade_only_exam_no_scale(tenant, batch, eg, "Activity - Communication Skills")
        for s in students:
            ExamScore.objects.create(tenant=tenant, exam=exam, student=s, marks=None, is_absent=False)

        assert not MarkSubmission.objects.filter(exam=exam).exists()

        resp = admin_client.post(undo_url(exam.id))
        assert resp.status_code == 200, resp.content
        data = resp.json()
        assert data['success'] is True

        submission = MarkSubmission.objects.get(exam=exam)
        assert submission.status == MarkSubmission.STATUS_DRAFT
        assert submission.submitted_by is None
        assert submission.submitted_at is None
        assert ExamScore.objects.filter(exam=exam).count() == 2

    def test_undo_partial_scores_still_reports_not_submitted(self, admin_client, tenant, academic_year):
        batch = _ordinary_batch(tenant, academic_year)
        eg = ExamGroup.objects.create(
            tenant=tenant, name=f"Plan {uuid.uuid4().hex[:4]}", batch=batch,
            exam_type="TERM", exam_date=date.today(), is_published=True,
        )
        students = _students(batch, tenant, 2)
        exam = _grade_only_exam_no_scale(tenant, batch, eg, "Activity - Partial")
        ExamScore.objects.create(tenant=tenant, exam=exam, student=students[0], marks=None, is_absent=False)

        resp = admin_client.post(undo_url(exam.id))
        data = resp.json()
        assert data['success'] is False
        assert not MarkSubmission.objects.filter(exam=exam).exists()


@pytest.mark.django_db
@pytest.mark.integration
class TestExamGroupMarksEntryUndoButton:
    """End-to-end regression for the reported bug: the Undo Submission
    button rendered for a normal exam but not for an activity-planner-style
    exam with no MarkSubmission/SkillsSubmission row, even though the badge
    showed "Submitted" for both."""

    def test_undo_button_renders_for_inferred_submitted_exam_only(self, admin_client, tenant, academic_year):
        batch = _ordinary_batch(tenant, academic_year)
        eg = ExamGroup.objects.create(
            tenant=tenant, name=f"Plan {uuid.uuid4().hex[:4]}", batch=batch,
            exam_type="TERM", exam_date=date.today(), is_published=True,
        )
        students = _students(batch, tenant, 2)

        full_exam = _grade_only_exam_no_scale(tenant, batch, eg, "Activity - Full")
        for s in students:
            ExamScore.objects.create(tenant=tenant, exam=full_exam, student=s, marks=None, is_absent=False)

        partial_exam = _grade_only_exam_no_scale(tenant, batch, eg, "Activity - Partial")
        ExamScore.objects.create(tenant=tenant, exam=partial_exam, student=students[0], marks=None, is_absent=False)

        resp = admin_client.get(f'/marks/exam-group/{eg.id}/')
        assert resp.status_code == 200, resp.content
        content = resp.content.decode()
        # Count actual rendered buttons via their onclick handler, not the
        # literal string "Undo Submission" — that also appears twice in the
        # page's static JS (the confirmation dialog's heading/okLabel),
        # regardless of how many buttons rendered.
        assert content.count('onclick="undoSubmission(') == 1
        assert f"undoSubmission('{full_exam.id}'" in content
        assert f"undoSubmission('{partial_exam.id}'" not in content
