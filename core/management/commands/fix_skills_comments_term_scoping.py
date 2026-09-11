"""
Repair SkillsTeacherComment rows orphaned by the term-scoping fix.

``portal.selectors.resolve_term`` used to resolve a term by name alone,
picking an arbitrary ``Term`` row across the whole tenant (Term.name isn't
globally unique — every batch's exam group has its own "Term 1", "Term 2",
etc.). Once call sites were fixed to scope the lookup to the correct batch,
any SkillsTeacherComment row saved under the old, wrong Term became invisible
to the portal (comment + signature both live on that one row, keyed by
student+batch+term) — indistinguishable from deletion in the UI, though the
row is still in the database.

This command finds those mis-scoped rows and re-points them at the Term the
app now actually reads from.

Usage:
    # Dry run
    python manage.py fix_skills_comments_term_scoping --tenant=<schema>

    # Apply
    python manage.py fix_skills_comments_term_scoping --tenant=<schema> --execute
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context


class Command(BaseCommand):
    help = "Re-point SkillsTeacherComment rows orphaned by the batch-scoped term-resolution fix."

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

    def _fix(self, execute: bool):
        from core.models import SkillsTeacherComment, Term

        rows = list(
            SkillsTeacherComment.objects.filter(term__isnull=False)
            .select_related("term__exam_group", "batch", "student")
        )

        repaired = []       # (row, correct_term) — no conflicting target, safe re-point
        merged = []          # (row, target) — target was blank, comment/signature copied over
        needs_review = []    # (row, target) — both sides have content, left untouched
        no_correct_term = [] # row — batch has no Term matching that name
        mis_scoped_count = 0

        for row in rows:
            if row.term.exam_group.batch_id == row.batch_id:
                continue  # already correctly scoped
            mis_scoped_count += 1

            # Scoped lookup only — NOT selectors.resolve_term(), which falls back to
            # an arbitrary tenant-wide same-named Term when the batch has none of its
            # own. That fallback can return this row's own (wrong) term, which would
            # silently look "already correct" and vanish from every bucket below.
            correct_term = Term.objects.filter(
                name__iexact=row.term.name, exam_group__batch=row.batch
            ).first()
            if correct_term is None:
                no_correct_term.append(row)
                continue

            target = (
                SkillsTeacherComment.objects.filter(
                    tenant=row.tenant,
                    student_id=row.student_id,
                    batch_id=row.batch_id,
                    term=correct_term,
                )
                .exclude(pk=row.pk)
                .first()
            )

            if target is None:
                repaired.append((row, correct_term))
            elif not target.comment and not target.signature_image:
                merged.append((row, target))
            else:
                needs_review.append((row, target))

        self.stdout.write(f"Mis-scoped rows found: {mis_scoped_count}")
        self.stdout.write(f"  Repairable (re-point):     {len(repaired)}")
        self.stdout.write(f"  Repairable (merge blank):  {len(merged)}")
        self.stdout.write(f"  Needs manual review:       {len(needs_review)}")
        self.stdout.write(f"  No matching term on batch: {len(no_correct_term)}")

        if repaired:
            self.stdout.write("\nSample re-points (first 10):")
            for row, correct_term in repaired[:10]:
                self.stdout.write(
                    f"  student={row.student_id} batch={row.batch_id} "
                    f"'{row.term.name}' (term={row.term_id}) -> (term={correct_term.id})"
                )

        if merged:
            self.stdout.write("\nSample merges into blank target (first 10):")
            for row, target in merged[:10]:
                self.stdout.write(
                    f"  student={row.student_id} batch={row.batch_id} "
                    f"orphan(term={row.term_id}) -> target(term={target.term_id}, pk={target.pk})"
                )

        if needs_review:
            self.stdout.write(self.style.WARNING("\nConflicts needing manual review:"))
            for row, target in needs_review:
                self.stdout.write(
                    f"  student={row.student_id} batch={row.batch_id} "
                    f"orphan(pk={row.pk}, term={row.term_id}, updated_at={row.updated_at}, "
                    f"comment_len={len(row.comment)}, has_signature={bool(row.signature_image)}) "
                    f"vs target(pk={target.pk}, term={target.term_id}, updated_at={target.updated_at}, "
                    f"comment_len={len(target.comment)}, has_signature={bool(target.signature_image)})"
                )

        if no_correct_term:
            self.stdout.write(self.style.WARNING("\nRows with no matching term on their batch (left untouched):"))
            for row in no_correct_term:
                self.stdout.write(
                    f"  student={row.student_id} batch={row.batch_id} term='{row.term.name}' (pk={row.pk})"
                )

        if not execute:
            self.stdout.write(self.style.WARNING("\nDry run complete. Pass --execute to apply."))
            return

        with transaction.atomic():
            for row, correct_term in repaired:
                row.term = correct_term
                row.save(update_fields=["term"])

            for row, target in merged:
                target.comment = row.comment
                target.signature_image = row.signature_image
                target.save(update_fields=["comment", "signature_image"])
                row.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Re-pointed {len(repaired)} row(s), merged {len(merged)} row(s). "
                f"{len(needs_review)} conflict(s) left for manual review."
            )
        )
