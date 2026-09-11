"""
Repair HomeworkAssessment / ProjectWorkAssessment / StudentActivity rows
mislabeled by the "current term" resolution bug.

``ReportGenerationService.resolve_exam_group_term`` used to return the first
Term ordinally (always "Term 1") regardless of what day it actually was. The
Teacher Portal's Activities feature resolves its ``term`` label the same way
for both saving and reading, so rows saved while the bug was live are
self-consistently labeled "Term 1" even when they were actually entered
during Term 2 or Term 3 — invisible under the term that's now resolved
correctly going forward.

This command finds rows whose stored ``term`` disagrees with what the fixed
resolver would have returned as of the row's own ``updated_at`` date, and
re-points the unambiguous ones. None of these three models carry a ``batch``
FK directly (they're scoped by student + term + academic_year), so the batch
is inferred from the student's current active BatchStudent membership in the
row's academic year.

Also lists (read-only — never auto-repaired) ReportTemplate rows whose baked
``.term`` disagrees with what the fixed resolver would have produced at
creation time, since that field is staff-editable and a blanket rewrite
risks clobbering an intentional customization.

Usage:
    # Dry run
    python manage.py fix_activities_term_scoping --tenant=<schema>

    # Apply
    python manage.py fix_activities_term_scoping --tenant=<schema> --execute
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Re-point Homework/Project/Activity rows mislabeled by the term-resolution bug."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--execute", action="store_true", default=False)

    def handle(self, *args, **options):
        schema = options["tenant"]
        execute = options["execute"]

        if not execute:
            self.stdout.write(self.style.WARNING("DRY RUN — pass --execute to apply\n"))

        with schema_context(schema):
            self._fix(execute)

    def _fix_model(self, model, execute: bool, *, unique_scope: bool) -> int:
        """``unique_scope``: True for models where (student, term, academic_year)
        is a DB-enforced unique key (HomeworkAssessment, ProjectWorkAssessment) —
        two repairable rows landing on the same target must be treated as a
        conflict with EACH OTHER, not just against pre-existing rows, or the
        second write 409s the whole batch. StudentActivity has no such
        constraint (a student can legitimately have several rows per term), so
        this extra check is skipped for it."""
        label = model.__name__
        rows = list(model.objects.select_related("student", "academic_year"))

        repairable = []   # (row, correct_term)
        conflicts = []    # (row, correct_term, target_pk_or_None)
        unresolved = 0     # couldn't determine a batch/exam-group/term for this row

        from core.services.report_generation_service import ReportGenerationService

        for row in rows:
            as_of = (row.updated_at or row.created_at).date()
            correct_term = ReportGenerationService.resolve_term_for_student(row.student, row.academic_year, as_of=as_of)
            if correct_term is None:
                unresolved += 1
                continue
            if correct_term == row.term:
                continue

            target = (
                model.objects.filter(
                    tenant=row.tenant, student=row.student, term=correct_term,
                    academic_year=row.academic_year,
                )
                .exclude(pk=row.pk)
                .first()
            )

            if target is None:
                repairable.append((row, correct_term))
            else:
                conflicts.append((row, correct_term, target.pk))

        if unique_scope:
            # Second pass: drop repairable rows that would collide with ANOTHER
            # repairable row from this same batch (same student+term+year target),
            # since detection above only checked against rows NOT being changed.
            by_target = {}
            for row, correct_term in repairable:
                key = (row.student_id, correct_term, row.academic_year_id)
                by_target.setdefault(key, []).append((row, correct_term))

            deduped = []
            for key, group in by_target.items():
                if len(group) == 1:
                    deduped.append(group[0])
                else:
                    for row, correct_term in group:
                        conflicts.append((row, correct_term, None))
            repairable = deduped

        self.stdout.write(f"\n{label}: {len(rows)} row(s) checked")
        self.stdout.write(f"  Repairable (re-point):     {len(repairable)}")
        self.stdout.write(f"  Conflicts (manual review): {len(conflicts)}")
        self.stdout.write(f"  No batch/term data found:  {unresolved}")

        if repairable:
            self.stdout.write("  Sample re-points (first 10):")
            for row, correct_term in repairable[:10]:
                self.stdout.write(
                    f"    student={row.student_id} pk={row.pk} "
                    f"'{row.term}' -> '{correct_term}'"
                )

        if conflicts:
            self.stdout.write(self.style.WARNING("  Conflicts needing manual review (first 10):"))
            for row, correct_term, target_pk in conflicts[:10]:
                where = f"already taken by target(pk={target_pk})" if target_pk else "collides with another row in this same repair batch"
                self.stdout.write(
                    f"    student={row.student_id} row(pk={row.pk}, term='{row.term}', "
                    f"updated_at={row.updated_at}) -> '{correct_term}' {where}"
                )

        if execute and repairable:
            with transaction.atomic():
                for row, correct_term in repairable:
                    row.term = correct_term
                    row.save(update_fields=["term"])

        return len(repairable)

    def _list_report_template_mismatches(self):
        """Read-only: list ReportTemplate rows whose baked ``.term`` disagrees
        with what the fixed resolver would compute as of creation."""
        from core.models import ReportTemplate, ExamGroup
        from core.services.report_generation_service import ReportGenerationService

        self.stdout.write("\nReportTemplate.term mismatches (listed only, not repaired):")
        mismatches = 0
        for template in ReportTemplate.objects.select_related("batch"):
            exam_group = (
                ExamGroup.objects.filter(batch=template.batch, is_published=True)
                .order_by("-exam_date")
                .first()
            )
            if exam_group is None:
                continue
            as_of = template.created_at.date()
            correct_term = ReportGenerationService.resolve_exam_group_term(exam_group, as_of=as_of)
            if correct_term and correct_term != (template.term or "").strip():
                mismatches += 1
                if mismatches <= 10:
                    self.stdout.write(
                        f"  template(pk={template.pk}, batch={template.batch_id}) "
                        f"term='{template.term}' -> would resolve to '{correct_term}' "
                        f"(created_at={template.created_at})"
                    )
        self.stdout.write(f"  Total mismatches: {mismatches}")

    def _fix(self, execute: bool):
        from core.models import HomeworkAssessment, ProjectWorkAssessment, StudentActivity

        total_repaired = 0
        for model in (HomeworkAssessment, ProjectWorkAssessment):
            total_repaired += self._fix_model(model, execute, unique_scope=True)
        # StudentActivity has no (student, term, academic_year) uniqueness — a
        # student can legitimately have several rows per term (one per
        # club/sport/activity), so within-batch collisions there are normal,
        # not a repair conflict.
        total_repaired += self._fix_model(StudentActivity, execute, unique_scope=False)

        self._list_report_template_mismatches()

        if not execute:
            self.stdout.write(self.style.WARNING("\nDry run complete. Pass --execute to apply."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nDone. Re-pointed {total_repaired} row(s)."))
