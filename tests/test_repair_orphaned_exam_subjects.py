"""Tests for repair_orphaned_exam_subjects.

Renaming a subject soft-deletes the old row and creates a new one, but the
exams created before the rename keep pointing at the old row. `Exam.subject` is
a forward FK, so it resolves the dead row fine and the admin gradebook still
shows the exam — while the portal, which reaches exams through
`Subject.employee`, loses it for the specialist who teaches the subject.

The repair moves those exams onto the live row. It must never silently create a
duplicate exam, never guess between two live rows, and never touch marks.
"""

import uuid
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import (
    Employee,
    Exam,
    ExamGroup,
    ExamScore,
    Student,
    Subject,
)
from portal.selectors import markable_exams_for_teacher


def _employee(tenant, tag):
    return Employee.objects.create(
        tenant=tenant,
        employee_number=f"E{uuid.uuid4().hex[:6].upper()}",
        joining_date=date(2020, 1, 1),
        first_name=tag,
        last_name="Specialist",
        gender=True,
        is_teaching_staff=True,
    )


def _exam_group(batch, tenant):
    return ExamGroup.objects.create(
        tenant=tenant, batch=batch, name=f"Plan {uuid.uuid4().hex[:4]}",
        exam_type="TERM", exam_date=date.today(), is_published=True,
    )


def _subject(batch, tenant, name, employee=None, deleted=False):
    subject = Subject.objects.create(
        tenant=tenant, batch=batch, name=name,
        code=f"S{uuid.uuid4().hex[:5].upper()}", employee=employee,
    )
    if deleted:
        Subject.all_objects.filter(pk=subject.pk).update(is_deleted=True)
        subject.refresh_from_db()
    return subject


def _exam(exam_group, subject, tenant, slot="EXAM"):
    now = timezone.now()
    return Exam.objects.create(
        tenant=tenant, exam_group=exam_group, subject=subject,
        exam_name=f"{slot} paper", start_time=now, end_time=now + timedelta(hours=2),
        maximum_marks=100, minimum_marks=40, weightage=100, assessment_slot=slot,
    )


def _run(tenant, **kwargs):
    out = StringIO()
    call_command(
        'repair_orphaned_exam_subjects',
        tenant=tenant.schema_name, stdout=out, **kwargs,
    )
    return out.getvalue()


@pytest.mark.django_db
@pytest.mark.unit
class TestRepairOrphanedExamSubjects:
    def _renamed_subject(self, batch, tenant, teacher):
        """The production shape: 'CTS - Music' renamed to 'CTS - Music‎' (a
        stray U+200E), old row soft-deleted and stripped of its teacher, the
        EXAM slot left behind on it while the newer slots landed on the live
        row."""
        dead = _subject(batch, tenant, "CTS - Music", employee=None, deleted=True)
        live = _subject(batch, tenant, "CTS - Music‎", employee=teacher)
        group = _exam_group(batch, tenant)
        orphan = _exam(group, dead, tenant, slot="EXAM")
        _exam(group, live, tenant, slot="ATTAINMENT")
        return dead, live, group, orphan

    def test_dry_run_changes_nothing(self, tenant, batch):
        teacher = _employee(tenant, "Dry")
        _dead, _live, _group, orphan = self._renamed_subject(batch, tenant, teacher)

        output = _run(tenant)

        assert "Orphaned exams re-pointed:   1" in output
        assert "Dry run complete" in output
        orphan.refresh_from_db()
        assert orphan.subject.is_deleted

    def test_execute_repoints_and_restores_portal_visibility(self, tenant, batch):
        """The whole point: after the repair the specialist can see the slot
        again."""
        teacher = _employee(tenant, "Fixed")
        _dead, live, _group, orphan = self._renamed_subject(batch, tenant, teacher)
        assert orphan.id not in {e.id for e in markable_exams_for_teacher(teacher)}

        _run(tenant, execute=True)

        orphan.refresh_from_db()
        assert orphan.subject_id == live.id
        assert orphan.id in {e.id for e in markable_exams_for_teacher(teacher)}

    def test_marks_survive_the_move(self, tenant, batch, student):
        teacher = _employee(tenant, "Marks")
        _dead, live, _group, orphan = self._renamed_subject(batch, tenant, teacher)
        score = ExamScore.objects.create(
            tenant=tenant, student=student, exam=orphan, marks=73,
        )

        _run(tenant, execute=True)

        score.refresh_from_db()
        assert score.marks == 73
        assert score.exam_id == orphan.id
        orphan.refresh_from_db()
        assert orphan.subject_id == live.id

    def test_rerun_is_a_noop(self, tenant, batch):
        teacher = _employee(tenant, "Rerun")
        self._renamed_subject(batch, tenant, teacher)
        _run(tenant, execute=True)

        output = _run(tenant, execute=True)

        assert "No exams are attached to a soft-deleted subject" in output

    def test_collision_is_reported_not_merged(self, tenant, batch, student):
        """Both rows holding the same slot means both may hold marks. Moving
        would create a duplicate exam and silently orphan one set of scores, so
        the command must refuse and hand it to a human."""
        teacher = _employee(tenant, "Clash")
        dead = _subject(batch, tenant, "Music", employee=None, deleted=True)
        live = _subject(batch, tenant, "Music‎", employee=teacher)
        group = _exam_group(batch, tenant)
        orphan = _exam(group, dead, tenant, slot="EXAM")
        existing = _exam(group, live, tenant, slot="EXAM")
        ExamScore.objects.create(tenant=tenant, student=student, exam=orphan, marks=11)

        output = _run(tenant, execute=True)

        assert "Blocked — target has this exam already: 1" in output
        assert "Orphaned exams re-pointed:   0" in output
        orphan.refresh_from_db()
        assert orphan.subject_id == dead.id
        assert Exam.objects.filter(exam_group=group, subject=live).count() == 1
        assert existing.subject_id == live.id

    def test_ambiguous_target_is_reported_not_guessed(self, tenant, batch):
        teacher = _employee(tenant, "Ambig")
        dead = _subject(batch, tenant, "Music", employee=None, deleted=True)
        _subject(batch, tenant, "Music‎", employee=teacher)
        _subject(batch, tenant, "M-u-s-i-c", employee=teacher)
        orphan = _exam(_exam_group(batch, tenant), dead, tenant)

        output = _run(tenant, execute=True)

        assert "Blocked — several live rows match:      1" in output
        orphan.refresh_from_db()
        assert orphan.subject_id == dead.id

    def test_no_live_row_is_reported(self, tenant, batch):
        dead = _subject(batch, tenant, "Retired Subject", employee=None, deleted=True)
        orphan = _exam(_exam_group(batch, tenant), dead, tenant)

        output = _run(tenant, execute=True)

        assert "Blocked — no live row to move to:       1" in output
        orphan.refresh_from_db()
        assert orphan.subject_id == dead.id

    def test_a_live_row_in_another_batch_is_not_a_target(self, tenant, batch, course, academic_year):
        """Name matching is scoped to the orphan's own batch — moving an exam
        onto another class's subject would be worse than leaving it."""
        from core.models import Batch

        other = Batch.objects.create(
            name=f"Other {uuid.uuid4().hex[:4]}", course=course,
            academic_year=academic_year,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330), tenant=tenant,
        )
        teacher = _employee(tenant, "Scoped")
        dead = _subject(batch, tenant, "Music", employee=None, deleted=True)
        _subject(other, tenant, "Music", employee=teacher)
        orphan = _exam(_exam_group(batch, tenant), dead, tenant)

        output = _run(tenant, execute=True)

        assert "Blocked — no live row to move to:       1" in output
        orphan.refresh_from_db()
        assert orphan.subject_id == dead.id

    def test_batch_filter_limits_scope(self, tenant, batch, course, academic_year):
        from core.models import Batch

        other = Batch.objects.create(
            name=f"Untouched {uuid.uuid4().hex[:4]}", course=course,
            academic_year=academic_year,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330), tenant=tenant,
        )
        teacher = _employee(tenant, "Scope")
        self._renamed_subject(batch, tenant, teacher)
        _dead2, _live2, _g2, orphan2 = self._renamed_subject(other, tenant, teacher)

        _run(tenant, batch=batch.name, execute=True)

        orphan2.refresh_from_db()
        assert orphan2.subject.is_deleted
