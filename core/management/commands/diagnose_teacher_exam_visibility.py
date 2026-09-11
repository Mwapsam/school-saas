"""
Explain, per exam, why a teacher can or cannot see it on the portal's marks
entry page.

Specialist teachers (Music, PE, …) reach an exam through ``Subject.employee``,
while class teachers get every exam in their batch. That difference, plus four
more gates, means an assessment can vanish for one teacher and one slot while
its siblings stay visible — which is invisible from the admin gradebook, since
the admin bypasses all of them.

Rather than re-deriving the rules (which would drift), this reports straight
from ``portal.selectors.explain_exam_visibility`` — the same function
``markable_exams_for_teacher`` uses to decide. It deliberately starts from
*every* exam in the batch instead of the selector's prefiltered queryset, so it
can also account for the rows the selector's SQL removes silently.

Read-only. Nothing here writes.

Usage:
    # Everything: every teacher who owns a subject, every batch
    python manage.py diagnose_teacher_exam_visibility --tenant=<schema>

    # One teacher, one class (name fragment or uuid)
    python manage.py diagnose_teacher_exam_visibility --tenant=<schema> \
        --teacher="Mtonga" --batch="5A"

    # Include the exams that ARE visible, for a full matrix
    python manage.py diagnose_teacher_exam_visibility --tenant=<schema> \
        --teacher="Simbeya" --include-visible
"""

import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django_tenants.utils import schema_context

# Normalising subject names for the duplicate scan: "Phys. Ed" and "Phys Ed"
# are the same subject to a human and should be reported together.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalise(name: str) -> str:
    return _NON_ALNUM.sub("", (name or "").lower())


def _looks_like_uuid(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F-]{32,36}", value or ""))


class Command(BaseCommand):
    help = (
        "Explain why each exam is or isn't visible to a teacher on the portal's "
        "marks entry page, naming the gate that excluded it."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--teacher", default=None,
                            help="Employee id, or a case-insensitive name fragment")
        parser.add_argument("--batch", default=None,
                            help="Batch id, or a case-insensitive name fragment")
        parser.add_argument("--include-visible", action="store_true", default=False,
                            help="Also list the exams the teacher CAN see")
        parser.add_argument("--summary-only", action="store_true", default=False,
                            help="Per-teacher gate tallies plus the structural "
                                 "summary, without the per-exam lines. Use this "
                                 "for a whole-tenant run — the per-exam listing "
                                 "runs to thousands of lines.")

    def handle(self, *args, **options):
        with schema_context(options["tenant"]):
            self._run(
                options["teacher"], options["batch"],
                options["include_visible"], options["summary_only"],
            )

    # ── Scope ────────────────────────────────────────────────────────────────

    def _teachers(self, needle):
        from core.models import Employee

        qs = Employee.objects.all()
        if needle:
            if _looks_like_uuid(needle):
                qs = qs.filter(id=needle)
            else:
                qs = qs.filter(
                    Q(first_name__icontains=needle) | Q(last_name__icontains=needle)
                )
        else:
            # Everyone who owns a subject — i.e. every teacher whose portal
            # access runs through the specialist path this command is about.
            qs = qs.filter(subjects_taught__is_deleted=False).distinct()
        return list(qs.order_by("first_name", "last_name"))

    def _batches(self, needle):
        from core.models import Batch

        qs = Batch.objects.filter(is_deleted=False).select_related("course", "academic_year")
        if needle:
            if _looks_like_uuid(needle):
                qs = qs.filter(id=needle)
            else:
                qs = qs.filter(name__icontains=needle)
        return list(qs.order_by("name"))

    # ── Report ───────────────────────────────────────────────────────────────

    def _run(self, teacher_needle, batch_needle, include_visible, summary_only=False):
        from core.models import BatchExamTypeConfiguration, Exam
        from portal import selectors

        teachers = self._teachers(teacher_needle)
        batches = self._batches(batch_needle)
        if not teachers:
            self.stdout.write(self.style.ERROR("No teacher matched."))
            return
        if not batches:
            self.stdout.write(self.style.ERROR("No batch matched."))
            return

        batch_ids = [b.id for b in batches]
        exams = list(
            Exam.objects.filter(exam_group__batch_id__in=batch_ids)
            .select_related(
                "subject", "subject__grading_scale", "subject__employee",
                # subject__batch: the subject need not belong to the same batch
                # as its exam group, and telling them apart is the point.
                "subject__batch",
                "grading_scale", "exam_group", "exam_group__batch",
                "exam_group__batch__course",
            )
            .order_by("exam_group__batch__name", "subject__name", "assessment_slot")
        )
        if not exams:
            self.stdout.write(self.style.WARNING(
                "No exams exist for the selected batch(es) — nothing to explain. "
                "If a teacher expected one here, it was never created in the exam planner."
            ))
        configs = {
            b.id: BatchExamTypeConfiguration.for_batch(b, b.tenant) for b in batches
        }

        for teacher in teachers:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n=== {teacher.full_name} ({teacher.id}) ==="
            ))
            # Derived once per teacher — the same set markable_exams_for_teacher
            # builds, so class-teacher membership is judged identically.
            ct_ids = {
                b.id for b in selectors.batches_for_teacher_as_class_teacher(teacher)
            }
            gate_counts = defaultdict(int)
            shown = 0

            for exam in exams:
                visible, gate, detail = selectors.explain_exam_visibility(
                    teacher, exam,
                    class_teacher_batch_ids=ct_ids,
                    config=configs[exam.exam_group.batch_id],
                )
                if visible:
                    gate_counts["VISIBLE"] += 1
                    if not include_visible:
                        continue
                else:
                    gate_counts[gate] += 1
                if summary_only:
                    continue

                shown += 1
                label = (
                    f"{exam.exam_group.batch.name} / "
                    f"{exam.subject.name if exam.subject_id else '—'} / "
                    f"{exam.assessment_slot or 'EXAM'}"
                )
                verdict = (
                    self.style.SUCCESS("VISIBLE") if visible
                    else self.style.WARNING(f"EXCLUDED: {gate}")
                )
                self.stdout.write(f"  {label:<48} exam={exam.id}  {verdict}")
                if detail:
                    self.stdout.write(f"      {detail}")
                if not visible:
                    self.stdout.write(
                        f"      subject={exam.subject_id} employee="
                        f"{getattr(exam.subject.employee, 'full_name', None) if exam.subject_id else None}"
                        f"  exam_group={exam.exam_group.name!r}"
                        f" published={exam.exam_group.is_published}"
                    )

            if not shown and not summary_only:
                self.stdout.write("  (nothing to report)")
            tally = "  ".join(
                f"{gate}={n}" for gate, n in sorted(gate_counts.items())
            )
            self.stdout.write(f"  {tally or 'no exams in scope'}")

        self._structural_summary(batches, exams)

    # ── Structural summary ───────────────────────────────────────────────────

    def _structural_summary(self, batches, exams):
        """The data shapes that cause the exclusions above, so the fix is
        obvious from the same output."""
        from core.models import ExamGroup, Subject

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Structural summary ==="))

        # Duplicate subject rows: the exam planner mirrors a subject into a
        # sibling batch when it can't name-match one, and the mirror is created
        # with no teacher — so a near-duplicate name splits a subject's exams
        # between an owned row and an invisible one.
        # all_objects, not objects: a soft-deleted row still owns its exams
        # (Exam.subject is a forward FK, so it bypasses ActiveSubjectManager),
        # and a rename that left the old row behind is one of the shapes that
        # splits a subject's slots across two rows.
        dupes = []
        for batch in batches:
            by_name = defaultdict(list)
            for subject in Subject.all_objects.filter(batch=batch).select_related("employee"):
                by_name[_normalise(subject.name)].append(subject)
            for _key, rows in by_name.items():
                if len(rows) > 1:
                    dupes.append((batch, rows))
        self.stdout.write(
            f"\nBatches with near-duplicate subject rows "
            f"(including soft-deleted): {len(dupes)}"
        )
        for batch, rows in dupes[:20]:
            self.stdout.write(f"  {batch.name}:")
            for s in rows:
                self.stdout.write(
                    f"    {s.id} {s.name!r} code={s.code!r} "
                    f"employee={getattr(s.employee, 'full_name', None)} "
                    f"deleted={s.is_deleted}"
                )

        # Cross-batch name variants. `_matching_subject` matches the *source*
        # batch's subject name against the target batch with `name__iexact`, so
        # a stray zero-width or format character (U+200E and friends), a double
        # space or a different dash makes propagation miss and mint a fresh,
        # teacherless subject instead. The per-batch scan above cannot see this
        # — the two rows live in different batches, which is the whole point.
        variants = defaultdict(set)
        for subject in Subject.objects.filter(batch__in=batches, is_deleted=False):
            variants[_normalise(subject.name)].add(subject.name)
        split = {k: v for k, v in variants.items() if len(v) > 1}
        self.stdout.write(
            f"\nSubject names that differ only by invisible/punctuation "
            f"characters (these defeat exam propagation): {len(split)}"
        )
        for _key, names in list(split.items())[:20]:
            self.stdout.write("  " + " vs ".join(sorted(repr(n) for n in names)))
            for name in sorted(names):
                owners = (
                    Subject.objects.filter(
                        batch__in=batches, is_deleted=False, name=name,
                    )
                    .select_related("batch", "employee")
                    .order_by("batch__name")
                )
                for s in owners:
                    self.stdout.write(
                        f"      {s.batch.name} / {name!r} "
                        f"employee={getattr(s.employee, 'full_name', None)}"
                    )

        # Unowned subjects that nonetheless carry exams — invisible to every
        # specialist teacher, markable only by the batch's class teacher.
        unowned = list(
            Subject.objects.filter(
                batch__in=batches, is_deleted=False, employee__isnull=True
            )
            .annotate(n=Count("exams"))
            .filter(n__gt=0)
            .select_related("batch")
            .order_by("batch__name", "name")
        )
        self.stdout.write(f"\nSubjects with exams but no teacher assigned: {len(unowned)}")
        for s in unowned[:20]:
            self.stdout.write(f"  {s.batch.name} / {s.name!r} ({s.n} exam(s)) subject={s.id}")

        # LEVEL-scale exams by slot. An ATTAINMENT/EFFORT cluster here means the
        # planner was given a skills scale for a grade-only slot, which sends the
        # exam to the Skills page instead of marks entry.
        level_by_slot = defaultdict(list)
        for exam in exams:
            scale = exam.get_grading_scale()
            if scale is not None and scale.scale_type == "LEVEL":
                level_by_slot[exam.assessment_slot or "EXAM"].append(exam)
        self.stdout.write("\nLEVEL-scale exams by slot (these leave marks entry):")
        if not level_by_slot:
            self.stdout.write("  none")
        for slot, rows in sorted(level_by_slot.items()):
            self.stdout.write(f"  {slot}: {len(rows)}")
            for exam in rows[:5]:
                scale = exam.get_grading_scale()
                self.stdout.write(
                    f"    {exam.exam_group.batch.name} / "
                    f"{exam.subject.name if exam.subject_id else '—'} "
                    f"scale={scale.name!r}"
                )

        # Two shapes that make a subject's slots split across rows the live
        # scans above cannot see. `Exam.subject` is a forward FK, so it resolves
        # soft-deleted rows and rows belonging to another batch quite happily —
        # and `markable_exams_for_teacher` joins through it without checking
        # either, so what a teacher sees depends on which row the planner
        # happened to attach each slot to.
        orphaned = [e for e in exams if e.subject_id and e.subject.is_deleted]
        self.stdout.write(
            f"\nExams attached to a SOFT-DELETED subject: {len(orphaned)}"
        )
        for exam in orphaned[:20]:
            self.stdout.write(
                f"  {exam.exam_group.batch.name} / {exam.subject.name!r} / "
                f"{exam.assessment_slot or 'EXAM'} "
                f"employee={getattr(exam.subject.employee, 'full_name', None)} "
                f"exam={exam.id} subject={exam.subject_id}"
            )

        foreign = [
            e for e in exams
            if e.subject_id and e.subject.batch_id != e.exam_group.batch_id
        ]
        self.stdout.write(
            f"\nExams whose subject belongs to a DIFFERENT batch than their "
            f"exam group: {len(foreign)}"
        )
        for exam in foreign[:20]:
            self.stdout.write(
                f"  exam group in {exam.exam_group.batch.name} but subject "
                f"{exam.subject.name!r} belongs to {exam.subject.batch.name} "
                f"/ {exam.assessment_slot or 'EXAM'} exam={exam.id}"
            )

        # Unactivated exam groups holding exams.
        unpublished = list(
            ExamGroup.objects.filter(batch__in=batches, is_published=False)
            .annotate(n=Count("exams"))
            .filter(n__gt=0)
            .select_related("batch")
            .order_by("batch__name", "name")
        )
        self.stdout.write(f"\nUnactivated exam groups that contain exams: {len(unpublished)}")
        for g in unpublished[:20]:
            self.stdout.write(f"  {g.batch.name} / {g.name!r} ({g.n} exam(s)) group={g.id}")

        # Slot coverage: a slot every other subject in the batch has, but this
        # one doesn't, was never created rather than filtered out.
        self.stdout.write("\nSubjects missing a slot their batch otherwise uses:")
        gaps = 0
        by_batch = defaultdict(list)
        for exam in exams:
            by_batch[exam.exam_group.batch_id].append(exam)
        for batch in batches:
            rows = by_batch.get(batch.id, [])
            if not rows:
                continue
            slots = {e.assessment_slot or "EXAM" for e in rows}
            per_subject = defaultdict(set)
            subject_of = {}
            for e in rows:
                if not e.subject_id:
                    continue
                per_subject[e.subject_id].add(e.assessment_slot or "EXAM")
                subject_of[e.subject_id] = e.subject
            for subject_id, have in sorted(
                per_subject.items(), key=lambda kv: subject_of[kv[0]].name
            ):
                missing = slots - have
                if not missing:
                    continue
                gaps += 1
                subject = subject_of[subject_id]
                # Where the row actually lives is the whole story: two rows in
                # one batch is a duplicate, a row in another batch is
                # cross-batch contamination, a deleted row is an orphan.
                origin = []
                if subject.batch_id != batch.id:
                    origin.append(f"row lives in {subject.batch.name}")
                if subject.is_deleted:
                    origin.append("row is SOFT-DELETED")
                suffix = f"  [{'; '.join(origin)}]" if origin else ""
                self.stdout.write(
                    f"  {batch.name} / {subject.name!r} missing {sorted(missing)} "
                    f"(batch uses {sorted(slots)}) subject={subject_id}{suffix}"
                )
        if not gaps:
            self.stdout.write("  none")
