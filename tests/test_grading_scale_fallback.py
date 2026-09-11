"""Regression tests for Subject.get_grading_scale()'s course-name-inferred
fallback. Batch.default_grading_scale was added in migration 0039 and removed
in migration 0040, leaving the old fallback step permanently dead (always
None via the hasattr guard). This meant pre-grade batches (Reception,
Nursery, Kindergarten, ...) without an explicit LEVEL scale set directly on
the Subject/Exam were silently misclassified as regular numeric exams
everywhere get_grading_scale()/is_skills_exam() is consulted. The fix reuses
the same course-name keyword fallback report generation already relies on
(core.grading_utils.infer_report_layout) instead of the dead field.
"""

import uuid
from datetime import date, timedelta

import pytest
from django.utils import timezone

from core.models import (
    Batch,
    Course,
    Exam,
    ExamGroup,
    GradingScale,
    Subject,
)
from core.services.exam_service import ExamService


@pytest.fixture
def tenant(school, domain):
    return school


def _skill_levels_scale(tenant):
    return GradingScale.objects.create(
        tenant=tenant, name="Skill Levels", code="SKILL_LEVELS",
        scale_type="LEVEL", is_active=True,
    )


def _batch_for_course(course_name, academic_year, tenant):
    course = Course.objects.create(
        tenant=tenant, course_name=course_name, code=f"C{uuid.uuid4().hex[:6].upper()}",
    )
    return Batch.objects.create(
        tenant=tenant, name=f"BATCH-{uuid.uuid4().hex[:6].upper()}", course=course,
        academic_year=academic_year, start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
    )


@pytest.mark.django_db
@pytest.mark.unit
class TestGradingScaleFallback:

    def test_pregrade_batch_without_explicit_scale_resolves_to_skill_levels(self, tenant, academic_year):
        skill_scale = _skill_levels_scale(tenant)
        batch = _batch_for_course("Reception", academic_year, tenant)
        subject = Subject.objects.create(
            tenant=tenant, code=f"S{uuid.uuid4().hex[:4].upper()}", name="Numeracy", batch=batch,
        )

        assert subject.grading_scale is None
        assert subject.get_grading_scale() == skill_scale

    def test_ordinary_batch_without_explicit_scale_is_unaffected(self, tenant, academic_year):
        _skill_levels_scale(tenant)
        default_scale = GradingScale.objects.create(
            tenant=tenant, name="Default Numeric", code=f"NUM-{uuid.uuid4().hex[:4]}",
            scale_type="NUMERIC", is_active=True, is_default=True,
        )
        batch = _batch_for_course("Grade 5", academic_year, tenant)
        subject = Subject.objects.create(
            tenant=tenant, code=f"S{uuid.uuid4().hex[:4].upper()}", name="Maths", batch=batch,
        )

        assert subject.get_grading_scale() == default_scale

    def test_is_skills_exam_true_for_pregrade_exam_with_no_explicit_scale(self, tenant, academic_year):
        _skill_levels_scale(tenant)
        batch = _batch_for_course("Nursery", academic_year, tenant)
        subject = Subject.objects.create(
            tenant=tenant, code=f"S{uuid.uuid4().hex[:4].upper()}", name="Literacy", batch=batch,
        )
        exam_group = ExamGroup.objects.create(
            tenant=tenant, name=f"Plan {uuid.uuid4().hex[:4]}", batch=batch,
            exam_type="TERM", exam_date=date.today(),
        )
        exam = Exam.objects.create(
            tenant=tenant, exam_group=exam_group, subject=subject,
            start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=1),
            maximum_marks=100, minimum_marks=0, assessment_slot="EXAM",
        )

        assert ExamService(tenant).is_skills_exam(exam) is True

    def test_pregrade_batch_resolves_level_scale_under_a_different_code(self, tenant, academic_year):
        """infer_report_layout() only matches a scale under the exact seeded
        code (SKILL_LEVELS). A school whose LEVEL scale was created under a
        different code must still classify correctly via scale_type alone."""
        custom_level_scale = GradingScale.objects.create(
            tenant=tenant, name="Custom Levels", code=f"CUSTOM-{uuid.uuid4().hex[:4]}",
            scale_type="LEVEL", is_active=True,
        )
        batch = _batch_for_course("Kindergarten", academic_year, tenant)
        subject = Subject.objects.create(
            tenant=tenant, code=f"S{uuid.uuid4().hex[:4].upper()}", name="Numeracy", batch=batch,
        )

        assert subject.get_grading_scale() == custom_level_scale
