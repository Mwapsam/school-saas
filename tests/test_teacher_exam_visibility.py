"""Tests for markable-exam visibility on the teacher portal.

Specialist teachers (Music, PE, …) reach an exam only through
``Subject.employee``, while class teachers get every exam in their batch. Four
more gates sit behind that, and each can hide one assessment slot while leaving
its siblings visible — the shape behind the "Mr Mtonga can't see Examination for
5A" reports.

``explain_exam_visibility`` is the single source of truth for those gates, and
``markable_exams_for_teacher`` plus ``diagnose_teacher_exam_visibility`` both
defer to it. The equivalence test below is what keeps the diagnostic honest: if
the selector and the predicate ever disagree, the command reports a gate that
isn't the real reason and sends support chasing the wrong thing.
"""

import uuid
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import (
    BatchExamTypeConfiguration,
    Employee,
    Exam,
    ExamGroup,
    GradingScale,
    Subject,
)
from portal import selectors
from portal.selectors import (
    GATE_GROUP_UNPUBLISHED,
    GATE_LEVEL_SCALE,
    GATE_NO_ACCESS,
    GATE_TYPE_DISABLED,
    explain_exam_visibility,
    markable_exams_for_teacher,
)


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


def _exam_group(batch, tenant, published=True):
    return ExamGroup.objects.create(
        tenant=tenant,
        batch=batch,
        name=f"Plan {uuid.uuid4().hex[:4]}",
        exam_type="TERM",
        exam_date=date.today(),
        is_published=published,
    )


def _subject(batch, tenant, name, employee=None, grading_scale=None):
    return Subject.objects.create(
        tenant=tenant,
        batch=batch,
        name=name,
        code=f"{name[:3].upper()}{uuid.uuid4().hex[:3].upper()}",
        employee=employee,
        grading_scale=grading_scale,
    )


def _exam(exam_group, subject, tenant, slot="EXAM", grading_scale=None):
    now = timezone.now()
    return Exam.objects.create(
        tenant=tenant,
        exam_group=exam_group,
        subject=subject,
        exam_name=f"{slot} paper",
        start_time=now,
        end_time=now + timedelta(hours=2),
        maximum_marks=100,
        minimum_marks=40,
        weightage=100,
        grading_scale=grading_scale,
        assessment_slot=slot,
    )


def _scale(tenant, scale_type):
    return GradingScale.objects.create(
        tenant=tenant,
        name=f"{scale_type} scale",
        code=f"{scale_type[:3]}{uuid.uuid4().hex[:4].upper()}",
        scale_type=scale_type,
    )


@pytest.mark.django_db
@pytest.mark.unit
class TestVisibilityGates:
    """One test per gate: the predicate names it, and the selector agrees by
    leaving the exam out."""

    def test_specialist_sees_their_own_subjects_exam(self, tenant, batch):
        teacher = _employee(tenant, "Owner")
        subject = _subject(batch, tenant, "Music", employee=teacher)
        exam = _exam(_exam_group(batch, tenant), subject, tenant)

        assert explain_exam_visibility(teacher, exam) == (True, "", "")
        assert exam.id in {e.id for e in markable_exams_for_teacher(teacher)}

    def test_no_access_when_subject_belongs_to_another_teacher(self, tenant, batch):
        """The specialist path is per Subject row — this is the gate the
        missing-assessment reports hinge on."""
        mine, theirs = _employee(tenant, "Mine"), _employee(tenant, "Theirs")
        subject = _subject(batch, tenant, "Music", employee=theirs)
        exam = _exam(_exam_group(batch, tenant), subject, tenant)

        visible, gate, detail = explain_exam_visibility(mine, exam)
        assert not visible
        assert gate == GATE_NO_ACCESS
        assert "another teacher" in detail
        assert exam.id not in {e.id for e in markable_exams_for_teacher(mine)}

    def test_no_access_when_subject_has_no_teacher(self, tenant, batch):
        """The exam planner mirrors subjects into sibling batches without an
        employee; those rows are invisible to every specialist."""
        teacher = _employee(tenant, "Orphan")
        subject = _subject(batch, tenant, "Music", employee=None)
        exam = _exam(_exam_group(batch, tenant), subject, tenant)

        visible, gate, detail = explain_exam_visibility(teacher, exam)
        assert not visible
        assert gate == GATE_NO_ACCESS
        assert "no teacher assigned" in detail

    def test_class_teacher_sees_a_subject_they_do_not_own(self, tenant, batch):
        class_teacher, specialist = _employee(tenant, "Class"), _employee(tenant, "Spec")
        batch.class_teachers.add(class_teacher)
        subject = _subject(batch, tenant, "Music", employee=specialist)
        exam = _exam(_exam_group(batch, tenant), subject, tenant)

        assert explain_exam_visibility(class_teacher, exam)[0]
        assert exam.id in {e.id for e in markable_exams_for_teacher(class_teacher)}

    def test_group_unpublished(self, tenant, batch):
        teacher = _employee(tenant, "Owner")
        subject = _subject(batch, tenant, "Music", employee=teacher)
        exam = _exam(_exam_group(batch, tenant, published=False), subject, tenant)

        visible, gate, _detail = explain_exam_visibility(teacher, exam)
        assert not visible
        assert gate == GATE_GROUP_UNPUBLISHED
        assert exam.id not in {e.id for e in markable_exams_for_teacher(teacher)}

    def test_level_scale_on_the_exam_hides_one_slot_only(self, tenant, batch):
        """`Exam.grading_scale` is per exam, so a LEVEL scale picked for
        ATTAINMENT sends that slot to the Skills page while EXAM stays on marks
        entry — one of the ways a single slot goes missing."""
        teacher = _employee(tenant, "Owner")
        subject = _subject(batch, tenant, "Phys Ed", employee=teacher)
        group = _exam_group(batch, tenant)
        exam_slot = _exam(group, subject, tenant, slot="EXAM")
        attainment = _exam(
            group, subject, tenant, slot="ATTAINMENT",
            grading_scale=_scale(tenant, "LEVEL"),
        )

        visible, gate, detail = explain_exam_visibility(teacher, attainment)
        assert not visible
        assert gate == GATE_LEVEL_SCALE
        assert "exam.grading_scale" in detail

        marked = {e.id for e in markable_exams_for_teacher(teacher)}
        assert exam_slot.id in marked
        assert attainment.id not in marked

    def test_level_scale_inherited_from_the_subject(self, tenant, batch):
        teacher = _employee(tenant, "Owner")
        subject = _subject(
            batch, tenant, "Phys Ed", employee=teacher,
            grading_scale=_scale(tenant, "LEVEL"),
        )
        exam = _exam(_exam_group(batch, tenant), subject, tenant)

        visible, gate, detail = explain_exam_visibility(teacher, exam)
        assert not visible
        assert gate == GATE_LEVEL_SCALE
        assert "subject.grading_scale" in detail

    def test_type_disabled_for_the_batch(self, tenant, batch):
        teacher = _employee(tenant, "Owner")
        subject = _subject(batch, tenant, "Music", employee=teacher)
        exam = _exam(_exam_group(batch, tenant), subject, tenant)
        BatchExamTypeConfiguration.objects.create(
            tenant=tenant, batch=batch, enable_traditional_exams=False,
        )

        visible, gate, _detail = explain_exam_visibility(teacher, exam)
        assert not visible
        assert gate == GATE_TYPE_DISABLED
        assert exam.id not in {e.id for e in markable_exams_for_teacher(teacher)}

    def test_config_cannot_hide_attainment_while_leaving_exam_visible(self, tenant, batch):
        """ATTAINMENT and EFFORT ride on `enable_traditional_exams`, the same
        flag as EXAM, so the batch config can only ever hide all three at once.
        This is what rules the config out as the cause of a single missing
        slot — pinned so the mapping isn't quietly changed."""
        teacher = _employee(tenant, "Owner")
        subject = _subject(batch, tenant, "Music", employee=teacher)
        group = _exam_group(batch, tenant)
        exams = {
            slot: _exam(group, subject, tenant, slot=slot)
            for slot in ("EXAM", "ATTAINMENT", "EFFORT")
        }
        BatchExamTypeConfiguration.objects.create(
            tenant=tenant, batch=batch, enable_traditional_exams=False,
        )

        gates = {
            slot: explain_exam_visibility(teacher, exam)[1]
            for slot, exam in exams.items()
        }
        assert gates == {slot: GATE_TYPE_DISABLED for slot in exams}


@pytest.mark.django_db
@pytest.mark.unit
class TestSelectorPredicateEquivalence:
    """`markable_exams_for_teacher` prefilters in SQL and `explain_exam_visibility`
    decides. What these tests catch is *prefilter drift*: a filter added to the
    queryset without a matching gate, so the selector drops an exam the predicate
    calls visible and the diagnostic then reports the wrong reason (or none).

    They cannot catch a change inside the predicate itself — both sides read it —
    and they shouldn't: that is what TestVisibilityGates is for. The fixture
    therefore needs a genuinely visible exam in *every* slot, or a slot-shaped
    filter slips through unnoticed.
    """

    def test_selector_matches_the_predicate_across_every_gate(self, tenant, batch):
        teacher, other = _employee(tenant, "Owner"), _employee(tenant, "Other")
        mine = _subject(batch, tenant, "Music", employee=teacher)
        not_mine = _subject(batch, tenant, "History", employee=other)
        unowned = _subject(batch, tenant, "Art", employee=None)
        published = _exam_group(batch, tenant)
        unpublished = _exam_group(batch, tenant, published=False)

        all_exams = [
            # One genuinely visible exam per slot, so a slot-shaped filter added
            # to the selector's SQL (and not to the predicate) shows up here.
            _exam(published, mine, tenant, slot="EXAM"),
            _exam(published, mine, tenant, slot="ATTAINMENT"),
            _exam(published, mine, tenant, slot="EFFORT"),
            _exam(published, mine, tenant, slot="CLASSWORK"),
            # …and one exam per gate.
            _exam(published, mine, tenant, slot="TEST",
                  grading_scale=_scale(tenant, "LEVEL")),
            _exam(unpublished, mine, tenant, slot="EXAM"),
            _exam(published, not_mine, tenant, slot="EXAM"),
            _exam(published, unowned, tenant, slot="EXAM"),
        ]

        from_selector = {e.id for e in markable_exams_for_teacher(teacher)}
        from_predicate = {
            e.id for e in all_exams if explain_exam_visibility(teacher, e)[0]
        }
        assert from_selector == from_predicate
        # Sanity: the fixture is actually exercising both outcomes.
        assert from_selector and len(from_selector) < len(all_exams)

    def test_equivalence_holds_for_a_class_teacher_too(self, tenant, batch):
        class_teacher, specialist = _employee(tenant, "Class"), _employee(tenant, "Spec")
        batch.class_teachers.add(class_teacher)
        subject = _subject(batch, tenant, "Music", employee=specialist)
        group = _exam_group(batch, tenant)
        all_exams = [
            _exam(group, subject, tenant, slot="EXAM"),
            _exam(_exam_group(batch, tenant, published=False), subject, tenant),
        ]

        from_selector = {e.id for e in markable_exams_for_teacher(class_teacher)}
        from_predicate = {
            e.id for e in all_exams if explain_exam_visibility(class_teacher, e)[0]
        }
        assert from_selector == from_predicate


@pytest.mark.django_db
@pytest.mark.unit
class TestDiagnoseCommand:
    def _run(self, tenant, **kwargs):
        out = StringIO()
        call_command(
            'diagnose_teacher_exam_visibility',
            tenant=tenant.schema_name, stdout=out, **kwargs,
        )
        return out.getvalue()

    def test_reports_the_gate_that_excluded_the_exam(self, tenant, batch):
        teacher = _employee(tenant, "Mtongalike")
        subject = _subject(batch, tenant, "Music", employee=teacher)
        _exam(
            _exam_group(batch, tenant), subject, tenant, slot="ATTAINMENT",
            grading_scale=_scale(tenant, "LEVEL"),
        )

        output = self._run(tenant, teacher="Mtongalike", batch=batch.name)
        assert GATE_LEVEL_SCALE in output
        assert "ATTAINMENT" in output

    def test_split_subject_rows_are_reported_as_no_access_and_flagged(self, tenant, batch):
        """The exam planner's mirror path can leave a batch holding both an
        owned subject row and an unowned near-duplicate, with the exams split
        between them. Only the owned half reaches the portal, and the duplicate
        pair is what explains it."""
        teacher = _employee(tenant, "Simbeyalike")
        owned = _subject(batch, tenant, "Physical Education", employee=teacher)
        mirrored = _subject(batch, tenant, "Physical-Education", employee=None)
        group = _exam_group(batch, tenant)
        _exam(group, owned, tenant, slot="EXAM")
        _exam(group, mirrored, tenant, slot="EFFORT")

        output = self._run(tenant, teacher="Simbeyalike", batch=batch.name)
        assert GATE_NO_ACCESS in output
        assert "no teacher assigned" in output
        # The structural summary explains why: two rows for one subject.
        assert "near-duplicate subject rows" in output
        assert "Physical-Education" in output

    def test_include_visible_shows_both_outcomes(self, tenant, batch):
        teacher = _employee(tenant, "Verbose")
        subject = _subject(batch, tenant, "Music", employee=teacher)
        group = _exam_group(batch, tenant)
        _exam(group, subject, tenant, slot="EXAM")
        _exam(group, subject, tenant, slot="EFFORT",
              grading_scale=_scale(tenant, "LEVEL"))

        default = self._run(tenant, teacher="Verbose", batch=batch.name)
        verbose = self._run(
            tenant, teacher="Verbose", batch=batch.name, include_visible=True,
        )

        def visible_exam_lines(output):
            return [ln for ln in output.splitlines() if "exam=" in ln and "VISIBLE" in ln]

        summary = self._run(
            tenant, teacher="Verbose", batch=batch.name, summary_only=True,
        )

        assert visible_exam_lines(default) == []
        assert len(visible_exam_lines(verbose)) == 1
        # --summary-only drops every per-exam line but keeps the tally and the
        # structural sections, so a whole-tenant run stays readable.
        assert "exam=" not in summary
        assert "VISIBLE=1" in summary
        assert "Structural summary" in summary
        # The per-teacher tally counts them either way, so a run that lists
        # nothing still says how much it looked at.
        assert "VISIBLE=1" in default
        assert f"{GATE_LEVEL_SCALE}=1" in default

    def test_invisible_character_name_variants_are_flagged(self, tenant, batch, course, academic_year):
        """A U+200E in one batch's subject name makes `_matching_subject`'s
        `name__iexact` miss, so the planner mints a teacherless duplicate in the
        other batch. The two rows are in different batches, so only the
        cross-batch variant scan catches it — and repr() is what makes the
        character visible in the report."""
        from core.models import Batch

        other = Batch.objects.create(
            name=f"Sibling {uuid.uuid4().hex[:4]}",
            course=course, academic_year=academic_year,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            tenant=tenant,
        )
        teacher = _employee(tenant, "Variant")
        _subject(batch, tenant, "Verbal Reasoning", employee=teacher)
        _subject(other, tenant, "Verbal Reasoning‎", employee=None)

        output = self._run(tenant, teacher="Variant")
        assert "differ only by invisible/punctuation characters" in output
        assert "\\u200e" in output or "‎" in repr(output)

    def test_slots_split_across_a_soft_deleted_row_are_explained(self, tenant, batch):
        """A rename that left the old subject row behind splits a subject's
        slots: the old exams stay on the soft-deleted row, the new ones land on
        the live one. `Exam.subject` is a forward FK so it resolves the deleted
        row happily, which is why every scan that filters `is_deleted=False`
        misses this and the slot gap looks inexplicable."""
        teacher = _employee(tenant, "Renamed")
        old = _subject(batch, tenant, "CTS - Music", employee=teacher)
        new = _subject(batch, tenant, "CTS - Music‎", employee=teacher)
        Subject.all_objects.filter(pk=old.pk).update(is_deleted=True)
        group = _exam_group(batch, tenant)
        _exam(group, old, tenant, slot="EXAM")
        _exam(group, new, tenant, slot="ATTAINMENT")
        _exam(group, new, tenant, slot="EFFORT")

        output = self._run(tenant, teacher="Renamed", batch=batch.name)
        assert "Exams attached to a SOFT-DELETED subject: 1" in output
        assert "row is SOFT-DELETED" in output
        # The duplicate scan has to see the deleted row too, or the pair that
        # explains the split is invisible.
        assert "near-duplicate subject rows (including soft-deleted): 1" in output

    def test_exam_pointing_at_another_batchs_subject_is_flagged(
        self, tenant, batch, course, academic_year
    ):
        from core.models import Batch

        other = Batch.objects.create(
            name=f"Other {uuid.uuid4().hex[:4]}",
            course=course, academic_year=academic_year,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=330),
            tenant=tenant,
        )
        teacher = _employee(tenant, "Foreign")
        foreign_subject = _subject(other, tenant, "Music", employee=teacher)
        _exam(_exam_group(batch, tenant), foreign_subject, tenant)

        output = self._run(tenant, teacher="Foreign", batch=batch.name)
        assert "belongs to a DIFFERENT batch than their exam group: 1" in output
        assert f"belongs to {other.name}" in output

    def test_unactivated_group_holding_exams_is_flagged(self, tenant, batch):
        teacher = _employee(tenant, "Unpub")
        subject = _subject(batch, tenant, "Music", employee=teacher)
        _exam(_exam_group(batch, tenant, published=False), subject, tenant)

        output = self._run(tenant, teacher="Unpub", batch=batch.name)
        assert GATE_GROUP_UNPUBLISHED in output
        assert "Unactivated exam groups that contain exams: 1" in output

    def test_command_writes_nothing(self, tenant, batch):
        """Read-only: support runs this against production."""
        teacher = _employee(tenant, "ReadOnly")
        subject = _subject(batch, tenant, "Music", employee=teacher)
        exam = _exam(_exam_group(batch, tenant), subject, tenant)
        before = (exam.assessment_slot, exam.grading_scale_id, subject.employee_id)

        self._run(tenant, teacher="ReadOnly", batch=batch.name)

        exam.refresh_from_db()
        subject.refresh_from_db()
        assert (exam.assessment_slot, exam.grading_scale_id, subject.employee_id) == before
        assert Exam.objects.filter(exam_group__batch=batch).count() == 1
        assert Subject.objects.filter(batch=batch).count() == 1
