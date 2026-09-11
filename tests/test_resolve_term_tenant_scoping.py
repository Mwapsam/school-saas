"""Regression test for portal.selectors.resolve_term's tenant-scoped fallback.

Term rows for every school live in one shared table (core is a SHARED_APPS
app), and TenantAwareManager's implicit per-request tenant filter is not
active outside a real request — e.g. inside django_tenants.utils.schema_context,
which management commands like reconcile_teacher_comments use. resolve_term's
final fallback must filter by tenant explicitly rather than by name alone, or
it can return a different school's Term row (and callers like
TeacherCommentService.resolve_skills_term can go on to write it onto this
tenant's data).
"""
import uuid
from datetime import date, timedelta

import pytest
from django_tenants.utils import schema_context

from core.models import AcademicYear, Batch, Course, ExamGroup, School, Term
from portal import selectors


def _school(tag):
    return School.objects.create(
        name=f"Resolve Term School {tag}",
        code=f"RT{tag}{uuid.uuid4().hex[:4].upper()}",
        schema_name=f"rt_{tag.lower()}_{uuid.uuid4().hex[:6]}",
    )


def _academic_year(school):
    return AcademicYear.objects.create(
        name=f"AY-{uuid.uuid4().hex[:4].upper()}",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        is_active=True,
        tenant=school,
    )


def _batch(school):
    course = Course.objects.create(
        course_name="Course", code=f"C{uuid.uuid4().hex[:5].upper()}", tenant=school,
    )
    return Batch.objects.create(
        name=f"BATCH-{uuid.uuid4().hex[:6].upper()}",
        course=course,
        academic_year=_academic_year(school),
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        tenant=school,
    )


def _batch_with_term(school, term_name):
    batch = _batch(school)
    eg = ExamGroup.objects.create(
        name=f"Exam Plan {uuid.uuid4().hex[:4]}", batch=batch,
        exam_type="TERM", exam_date=date.today(), tenant=school,
    )
    # Phase 3+: Terms are year-scoped, not per-batch. Use academic_year directly.
    term = Term.objects.create(
        tenant=school, academic_year=batch.academic_year, name=term_name,
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=30),
    )
    return batch, term


@pytest.mark.django_db
@pytest.mark.unit
class TestResolveTermTenantScoping:
    def test_fallback_never_crosses_tenant(self, db):
        school_a = _school("A")
        school_b = _school("B")
        # School B has a Term named "Term 1" that school A's batch does NOT
        # have of its own — this forces resolve_term's fallback branch.
        _, term_b = _batch_with_term(school_b, "Term 1")
        batch_a = _batch(school_a)

        result = selectors.resolve_term("Term 1", batch=batch_a)

        assert result != term_b
        assert result is None or result.tenant_id == school_a.id

    def test_fallback_matches_same_tenant_different_batch(self, db):
        """The fallback's intent (same tenant, different batch, name match)
        still works — only cross-tenant results are excluded."""
        school = _school("C")
        _, other_term = _batch_with_term(school, "Term 1")
        batch = _batch(school)

        result = selectors.resolve_term("Term 1", batch=batch)

        assert result == other_term

    def test_no_leak_inside_schema_context(self, tenant):
        """Reproduces the exact conditions reconcile_teacher_comments runs
        under: TenantAwareManager's implicit tenant filter is disabled for
        the FakeTenant that schema_context activates."""
        other_school = _school("D")
        _, other_term = _batch_with_term(other_school, "Term 1")
        batch = _batch(tenant)

        with schema_context(tenant.schema_name):
            result = selectors.resolve_term("Term 1", batch=batch)

        assert result != other_term
        assert result is None or result.tenant_id == tenant.id
