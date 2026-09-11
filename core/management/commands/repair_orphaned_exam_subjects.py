"""
Re-point exams that are still attached to a soft-deleted subject row.

Renaming a subject in this system leaves the old row behind, soft-deleted, and
creates a new one. Exams created before the rename keep pointing at the old row
— ``Exam.subject`` is a forward FK, so it resolves a soft-deleted row without
complaint and the admin gradebook carries on showing the exam. The teacher
portal does not: ``markable_exams_for_teacher`` reaches an exam through
``Subject.employee``, and the abandoned row usually lost its teacher, so the
assessment simply vanishes for the specialist who teaches it — one slot at a
time, since only the slots created before the rename are affected.

This moves each orphaned exam onto the live subject row for the same batch,
matched on a normalised name (case, spacing, punctuation and invisible format
characters such as U+200E ignored — a stray one of those is often what the
rename introduced). Marks are safe: ``ExamScore`` points at the exam, not the
subject, so nothing about a score changes.

An exam is never moved onto a row that already has an exam in the same group,
slot, name and code — that would create the duplicate the planner works to
avoid. Those are reported as conflicts and left alone for a human.

Dry run by default, like reconcile_teacher_comments.

Usage:
    python manage.py repair_orphaned_exam_subjects --tenant=<schema>
    python manage.py repair_orphaned_exam_subjects --tenant=<schema> --execute
    python manage.py repair_orphaned_exam_subjects --tenant=<schema> --batch=<uuid|name>
"""

import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

# Same normalisation the diagnostic uses: everything that is not a letter or a
# digit goes, which covers spacing, dashes and zero-width/format characters.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalise(name: str) -> str:
    return _NON_ALNUM.sub("", (name or "").lower())


def _looks_like_uuid(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F-]{32,36}", value or ""))


class Command(BaseCommand):
    help = (
        "Re-point exams left attached to a soft-deleted subject row onto the "
        "live subject for the same batch."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--execute", action="store_true", default=False)
        parser.add_argument("--batch", default=None,
                            help="Batch id, or a case-insensitive name fragment")

    def handle(self, *args, **options):
        if not options["execute"]:
            self.stdout.write(self.style.WARNING("DRY RUN — pass --execute to apply\n"))
        with schema_context(options["tenant"]):
            self._repair(options["execute"], options["batch"])

    def _repair(self, execute, batch_needle):
        from core.models import Batch, Exam, Subject

        batches = Batch.objects.filter(is_deleted=False)
        if batch_needle:
            if _looks_like_uuid(batch_needle):
                batches = batches.filter(id=batch_needle)
            else:
                batches = batches.filter(name__icontains=batch_needle)
        batch_ids = list(batches.values_list("id", flat=True))

        orphans = [
            e for e in Exam.objects.filter(exam_group__batch_id__in=batch_ids)
            .select_related(
                "subject", "subject__batch", "exam_group", "exam_group__batch",
            )
            .order_by("exam_group__batch__name", "subject__name", "assessment_slot")
            if e.subject_id and e.subject.is_deleted
        ]

        if not orphans:
            self.stdout.write(self.style.SUCCESS(
                "No exams are attached to a soft-deleted subject. Nothing to do."
            ))
            return

        # Live rows per (batch, normalised name) — the candidate targets.
        live: dict = {}
        for subject in Subject.objects.filter(batch_id__in=batch_ids).select_related("employee"):
            live.setdefault((subject.batch_id, _normalise(subject.name)), []).append(subject)

        moved, ambiguous, no_target, conflicts = [], [], [], []

        for exam in orphans:
            key = (exam.subject.batch_id, _normalise(exam.subject.name))
            candidates = live.get(key, [])
            if not candidates:
                no_target.append(exam)
                continue
            if len(candidates) > 1:
                # Two live rows normalise the same — picking one would be a
                # coin toss, and the wrong pick strands the marks somewhere new.
                ambiguous.append((exam, candidates))
                continue
            target = candidates[0]
            clash = (
                Exam.objects.filter(
                    exam_group=exam.exam_group,
                    subject=target,
                    assessment_slot=exam.assessment_slot,
                    exam_name=exam.exam_name,
                    exam_code=exam.exam_code,
                )
                .exclude(pk=exam.pk)
                .first()
            )
            if clash is not None:
                conflicts.append((exam, target, clash))
                continue
            moved.append((exam, target))

        if execute and moved:
            with transaction.atomic():
                for exam, target in moved:
                    exam.subject = target
                    exam.save(update_fields=["subject"])

        self._report(moved, conflicts, ambiguous, no_target, execute)

    def _report(self, moved, conflicts, ambiguous, no_target, execute):
        self.stdout.write(f"Orphaned exams re-pointed:   {len(moved)}")
        self.stdout.write(f"Blocked — target has this exam already: {len(conflicts)}")
        self.stdout.write(f"Blocked — several live rows match:      {len(ambiguous)}")
        self.stdout.write(f"Blocked — no live row to move to:       {len(no_target)}")

        if moved:
            self.stdout.write("\nRe-pointed:")
            for exam, target in moved:
                self.stdout.write(
                    f"  {exam.exam_group.batch.name} / {exam.assessment_slot or 'EXAM'} "
                    f"{exam.subject.name!r} -> {target.name!r} "
                    f"(now markable by {getattr(target.employee, 'full_name', None)}) "
                    f"exam={exam.id}"
                )

        if conflicts:
            self.stdout.write(self.style.WARNING(
                "\nLeft alone — the live row already has this exam. Both rows hold "
                "marks; decide which is authoritative before merging:"
            ))
            for exam, target, clash in conflicts:
                self.stdout.write(
                    f"  {exam.exam_group.batch.name} / {exam.assessment_slot or 'EXAM'} "
                    f"orphan exam={exam.id} ({exam.scores.count()} score(s)) vs "
                    f"existing exam={clash.id} ({clash.scores.count()} score(s)) "
                    f"on subject={target.id}"
                )

        if ambiguous:
            self.stdout.write(self.style.WARNING(
                "\nLeft alone — more than one live subject row matches; merge the "
                "duplicates first:"
            ))
            for exam, candidates in ambiguous:
                names = ", ".join(f"{c.name!r} ({c.id})" for c in candidates)
                self.stdout.write(
                    f"  {exam.exam_group.batch.name} / {exam.subject.name!r} -> {names}"
                )

        if no_target:
            self.stdout.write(self.style.WARNING(
                "\nLeft alone — no live subject row with a matching name in that "
                "batch. Recreate the subject, or reassign the exam by hand:"
            ))
            for exam in no_target:
                self.stdout.write(
                    f"  {exam.exam_group.batch.name} / {exam.subject.name!r} / "
                    f"{exam.assessment_slot or 'EXAM'} exam={exam.id}"
                )

        if not execute:
            self.stdout.write(self.style.WARNING(
                "\nDry run complete. Pass --execute to apply."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nDone. Re-pointed {len(moved)} exam(s); marks were not touched."
            ))
