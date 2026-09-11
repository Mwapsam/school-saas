"""Tests for per-teacher skills locking (Phase 5) — one teacher submitting doesn't block co-teachers."""

import pytest
from uuid import uuid4
from datetime import date, timedelta

from core.models import Employee, User, Batch, ExamGroup, Term
from portal.models import SkillsSubmission
from core.services.teacher_comment_service import TeacherCommentService


@pytest.fixture
def employee_a(db, school):
    """Create test employee A."""
    u = User(
        username=f"teacher_a_{uuid4().hex[:6]}",
        email=f"teacher_a_{uuid4().hex[:6]}@test.local",
        first_name="Alice",
        last_name="Teacher",
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(school)
    return Employee.objects.create(
        tenant=school,
        employee_number=f"E{uuid4().hex[:6].upper()}",
        joining_date="2020-01-01",
        first_name="Alice",
        last_name="Teacher",
        gender=True,
        is_teaching_staff=True,
        user=u
    )


@pytest.fixture
def employee_b(db, school):
    """Create test employee B."""
    u = User(
        username=f"teacher_b_{uuid4().hex[:6]}",
        email=f"teacher_b_{uuid4().hex[:6]}@test.local",
        first_name="Bob",
        last_name="Teacher",
    )
    u.set_password("testpass123")
    u.save()
    u.tenants.add(school)
    return Employee.objects.create(
        tenant=school,
        employee_number=f"E{uuid4().hex[:6].upper()}",
        joining_date="2020-01-01",
        first_name="Bob",
        last_name="Teacher",
        gender=False,
        is_teaching_staff=True,
        user=u
    )


def _exam_group(batch, tenant):
    """Create an exam group for a batch."""
    return ExamGroup.objects.create(
        tenant=tenant,
        batch=batch,
        name="Skills Assessment",
        exam_type="TERM",
        exam_date=date.today(),
    )


@pytest.mark.django_db
class TestPerTeacherSkillsLock:
    """Per-teacher skills locking tests."""

    def test_teacher_a_submission_does_not_block_teacher_b(self, school, batch, employee_a, employee_b):
        """Teacher A submitting doesn't block teacher B's still-draft work."""
        batch.class_teachers.add(employee_a, employee_b)

        eg = _exam_group(batch, school)
        # Phase 3+: Terms are year-scoped, not per-batch. Use academic_year directly.
        term = Term.objects.create(
            tenant=school,
            academic_year=batch.academic_year,
            name="Term 1",
            start_date="2025-01-01",
            end_date="2025-03-31",
        )

        # Teacher A submits
        SkillsSubmission.objects.create(
            tenant=school,
            batch=batch,
            term=term,
            employee=employee_a,
            status=SkillsSubmission.STATUS_SUBMITTED,
        )

        # Teacher B is not locked
        svc = TeacherCommentService(school)
        assert not svc.is_skills_locked(batch, term, employee=employee_b)

    def test_teacher_a_double_submit_rejected(self, school, batch, employee_a):
        """Teacher A double-submitting is rejected."""
        batch.employee = employee_a
        batch.save()

        eg = _exam_group(batch, school)
        # Phase 3+: Terms are year-scoped, not per-batch. Use academic_year directly.
        term = Term.objects.create(
            tenant=school,
            academic_year=batch.academic_year,
            name="Term 1",
            start_date="2025-01-01",
            end_date="2025-03-31",
        )

        # First submission
        SkillsSubmission.objects.create(
            tenant=school,
            batch=batch,
            term=term,
            employee=employee_a,
            status=SkillsSubmission.STATUS_SUBMITTED,
        )

        # Teacher A tries to submit again
        svc = TeacherCommentService(school)
        assert svc.is_skills_locked(batch, term, employee=employee_a)

    def test_admin_submission_blocks_everyone(self, school, batch, employee_a, employee_b):
        """Admin whole-batch submission (employee=None) blocks everyone."""
        batch.class_teachers.add(employee_a, employee_b)

        eg = _exam_group(batch, school)
        # Phase 3+: Terms are year-scoped, not per-batch. Use academic_year directly.
        term = Term.objects.create(
            tenant=school,
            academic_year=batch.academic_year,
            name="Term 1",
            start_date="2025-01-01",
            end_date="2025-03-31",
        )

        # Admin submits for the whole batch
        SkillsSubmission.objects.create(
            tenant=school,
            batch=batch,
            term=term,
            employee=None,  # Whole-batch/admin submission
            status=SkillsSubmission.STATUS_SUBMITTED,
        )

        svc = TeacherCommentService(school)
        # Both teachers blocked
        assert svc.is_skills_locked(batch, term, employee=employee_a)
        assert svc.is_skills_locked(batch, term, employee=employee_b)
        # Also blocked when checking with no employee (staff view)
        assert svc.is_skills_locked(batch, term, employee=None)

    def test_teacher_lock_does_not_block_other_term(self, school, batch, employee_a, employee_b):
        """Teacher A's lock on Term 1 doesn't affect Term 2."""
        batch.class_teachers.add(employee_a, employee_b)

        eg = _exam_group(batch, school)
        term1 = Term.objects.create(
            tenant=school,
            academic_year=batch.academic_year,
            name="Term 1",
            start_date="2025-01-01",
            end_date="2025-03-31",
        )
        term2 = Term.objects.create(
            tenant=school,
            academic_year=batch.academic_year,
            name="Term 2",
            start_date="2025-04-01",
            end_date="2025-06-30",
        )

        # Teacher A submits Term 1
        SkillsSubmission.objects.create(
            tenant=school,
            batch=batch,
            term=term1,
            employee=employee_a,
            status=SkillsSubmission.STATUS_SUBMITTED,
        )

        svc = TeacherCommentService(school)
        # Teacher A locked on Term 1
        assert svc.is_skills_locked(batch, term1, employee=employee_a)
        # But not on Term 2
        assert not svc.is_skills_locked(batch, term2, employee=employee_a)
