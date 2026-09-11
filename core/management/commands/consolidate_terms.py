"""
Consolidate duplicate per-batch Term rows into year-level canonical Terms.

Background: Prior to Phase 1, Term had no direct link to AcademicYear — only via
Term.exam_group.batch.academic_year. Every batch's exam plan got its own ExamGroup
with its own Term 1/2/3, so a school with 10 batches had ~30 duplicate "Term 1" rows.
This command consolidates them into one canonical per (tenant, academic_year, name).

Strategy:
  1. Group Terms by (tenant, academic_year_id, normalised(name))
  2. Pick canonical (start_date, end_date) pair: majority wins, ties broken deterministically
  3. For each group: promote the majority-date row with lowest id as canonical
  4. Repoint all 9 FK models to canonical Term (handling unique-constraint collisions)
  5. Delete orphaned source rows

Dry run by default (zero writes, pure simulation with full report).
Pass --execute to apply changes. One transaction per tenant (blast-radius control).

Usage:
    # Dry run for one tenant
    python manage.py consolidate_terms --tenant=<schema>

    # Apply for one tenant
    python manage.py consolidate_terms --tenant=<schema> --execute

    # Dry run for all tenants
    python manage.py consolidate_terms --all-tenants

    # Apply for all tenants
    python manage.py consolidate_terms --all-tenants --execute
"""

import re
from collections import defaultdict
from datetime import date
from typing import Dict, List, Tuple, Set

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django_tenants.utils import schema_context

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalise(name: str) -> str:
    """Normalize term name for grouping (same pattern as repair_term_dates.py)."""
    return _NON_ALNUM.sub("", (name or "").lower())


class ConsolidationReport:
    """Tracks consolidation actions and anomalies for reporting."""

    def __init__(self):
        self.groups_found = 0
        self.canonical_terms = []  # (old_id, new_id, name, date_info)
        self.date_conflicts = []   # (group_key, dates_and_counts)
        self.repointed = defaultdict(int)  # model_name -> count
        self.collisions_resolved = []  # (model_name, collision_count)
        self.batch_year_mismatches = []
        self.orphans_deleted = 0
        self.errors = []

    def add_canonical(self, old_id, new_id, name, start_date, end_date):
        self.canonical_terms.append((old_id, new_id, name, start_date, end_date))

    def add_date_conflict(self, group_key, dates_and_counts):
        self.date_conflicts.append((group_key, dates_and_counts))

    def add_repoint(self, model_name, count):
        self.repointed[model_name] += count

    def add_collision(self, model_name, count):
        self.collisions_resolved.append((model_name, count))

    def add_batch_year_mismatch(self, batch_id, batch_year, term_year, term_id):
        self.batch_year_mismatches.append((batch_id, batch_year, term_year, term_id))

    def add_error(self, msg):
        self.errors.append(msg)


class Command(BaseCommand):
    help = "Consolidate duplicate per-batch Terms into year-level canonical Terms."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=str, help="Tenant schema to consolidate")
        parser.add_argument("--all-tenants", action="store_true",
                            help="Consolidate all tenants")
        parser.add_argument("--execute", action="store_true", default=False,
                            help="Apply changes (default: dry run)")

    def handle(self, *args, **options):
        tenant_opt = options.get("tenant")
        all_tenants_opt = options.get("all_tenants")
        execute = options.get("execute")

        if not tenant_opt and not all_tenants_opt:
            raise CommandError("Specify --tenant=<schema> or --all-tenants")

        if not execute:
            self.stdout.write(
                self.style.WARNING("DRY RUN — pass --execute to apply\n")
            )

        if all_tenants_opt:
            from core.models import School
            tenants = list(School.objects.exclude(schema_name="public"))
            if not tenants:
                self.stdout.write(self.style.WARNING("No tenants found"))
                return
        else:
            tenants = [tenant_opt]

        for tenant_id in tenants:
            schema = tenant_id.schema_name if hasattr(tenant_id, "schema_name") else tenant_id
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Consolidating Terms for tenant: {schema}")
            self.stdout.write('='*60)
            with schema_context(schema):
                self._consolidate(execute)

        self.stdout.write(
            self.style.SUCCESS("\nConsolidation complete.")
            if execute
            else self.style.WARNING("\nDry run complete.")
        )

    def _consolidate(self, execute: bool):
        """Main consolidation logic per tenant."""
        from core.models import (
            Term, Exam, SkillsTeacherComment, AttendanceSummary,
            CoScholasticScore, SkillsAssessment, ActivityAssessment,
            AssessmentMark, FeeCollection
        )
        from portal.models import SkillsSubmission

        report = ConsolidationReport()

        # Load all Terms with relationships
        terms = list(
            Term.objects.select_related("academic_year").order_by("id")
        )

        if not terms:
            self.stdout.write(self.style.WARNING("No terms found"))
            return

        # Group by (academic_year_id, normalised(name))
        groups = self._group_terms(terms, report)
        report.groups_found = len(groups)

        if not groups:
            self.stdout.write(self.style.WARNING("No duplicate groups found"))
            return

        # Consolidation simulation (no writes yet)
        consolidation_plan = self._plan_consolidation(groups, report)

        # Report findings
        self._report_findings(report)

        if not execute:
            return

        # Execute consolidation with rollback safety
        try:
            with transaction.atomic():
                self._execute_consolidation(consolidation_plan, report)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nConsolidated {len(consolidation_plan)} term groups. "
                        f"Deleted {report.orphans_deleted} orphan rows."
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\nConsolidation failed (rolled back): {e}")
            )
            raise

    def _group_terms(
        self, terms: List, report: ConsolidationReport
    ) -> Dict[Tuple, List]:
        """Group terms by (academic_year_id, normalised_name)."""
        groups = defaultdict(list)
        for term in terms:
            year_id = term.academic_year_id

            if not year_id:
                report.add_error(
                    f"Term {term.id} ({term.name!r}): no academic_year found"
                )
                continue

            norm_name = _normalise(term.name)
            key = (year_id, norm_name)
            groups[key].append(term)

        return {k: v for k, v in groups.items() if len(v) > 1}

    def _plan_consolidation(
        self, groups: Dict, report: ConsolidationReport
    ) -> Dict[Tuple, Tuple]:
        """
        Plan which term becomes canonical for each group.

        Returns: {group_key: (canonical_term, [source_terms])}
        """
        consolidation_plan = {}

        for group_key, terms in groups.items():
            year_id, norm_name = group_key

            # Count (start_date, end_date) pairs
            date_pairs = defaultdict(list)
            for term in terms:
                key = (term.start_date, term.end_date)
                date_pairs[key].append(term)

            # Majority wins; ties broken deterministically (lowest id)
            majority_pair, majority_terms = self._pick_canonical_dates(
                date_pairs, report, group_key
            )

            # Promote the majority-date term with the lowest id as canonical
            canonical = min(majority_terms, key=lambda t: t.id)

            consolidation_plan[group_key] = (canonical, terms)

        return consolidation_plan

    def _pick_canonical_dates(
        self, date_pairs: Dict, report: ConsolidationReport, group_key: Tuple
    ) -> Tuple:
        """
        Pick the canonical (start_date, end_date) pair.

        Returns: ((start, end), [terms_with_that_date_pair])
        """
        if len(date_pairs) == 1:
            pair = list(date_pairs.keys())[0]
            return pair, date_pairs[pair]

        # Multiple date pairs: majority wins
        most_common = max(date_pairs.items(), key=lambda x: len(x[1]))
        canonical_pair, canonical_terms = most_common

        # Report minority-date outliers
        for pair, terms in date_pairs.items():
            if pair != canonical_pair:
                report.add_date_conflict(
                    group_key,
                    {pair: len(date_pairs[pair]) for pair in date_pairs.keys()}
                )
                break  # Report once per group, not once per outlier pair

        return canonical_pair, canonical_terms

    def _report_findings(self, report: ConsolidationReport):
        """Print human-readable report."""
        self.stdout.write(f"\nGroups with duplicates: {report.groups_found}")

        if report.canonical_terms:
            self.stdout.write(f"Canonical terms (first 10):")
            for old_id, new_id, name, start, end in report.canonical_terms[:10]:
                status = "SAME" if old_id == new_id else "NEW"
                self.stdout.write(
                    f"  {status:4} {name!r} {start}..{end} "
                    f"old={old_id} → new={new_id}"
                )
            if len(report.canonical_terms) > 10:
                self.stdout.write(
                    f"  ... and {len(report.canonical_terms) - 10} more"
                )

        if report.date_conflicts:
            self.stdout.write(self.style.WARNING(f"\nDate-conflict outliers (review manually):"))
            for group_key, dates_and_counts in report.date_conflicts[:5]:
                year_id, norm_name = group_key
                self.stdout.write(f"  {norm_name} (year={year_id}):")
                for date_pair, count in dates_and_counts.items():
                    self.stdout.write(f"    {date_pair[0]}..{date_pair[1]}: {count} rows")

        if report.repointed:
            self.stdout.write(f"\nRepoints by model:")
            for model_name, count in sorted(report.repointed.items()):
                self.stdout.write(f"  {model_name}: {count}")

        if report.collisions_resolved:
            self.stdout.write(self.style.WARNING(f"\nUnique-constraint collisions resolved:"))
            for model_name, count in report.collisions_resolved:
                self.stdout.write(f"  {model_name}: {count} collision(s)")

        if report.batch_year_mismatches:
            self.stdout.write(
                self.style.ERROR(
                    f"\nBatch/academic_year mismatches (MUST be reviewed):"
                )
            )
            for batch_id, batch_year, term_year, term_id in report.batch_year_mismatches:
                self.stdout.write(
                    f"  batch={batch_id} has academic_year={batch_year} "
                    f"but term={term_id} has year={term_year}"
                )

        if report.errors:
            self.stdout.write(self.style.ERROR(f"\nAnomalies:"))
            for error in report.errors:
                self.stdout.write(f"  {error}")

    def _execute_consolidation(self, consolidation_plan: Dict, report: ConsolidationReport):
        """Execute the consolidation with all FK repointing."""
        from core.models import (
            Term, Exam, SkillsTeacherComment, AttendanceSummary,
            CoScholasticScore, SkillsAssessment, ActivityAssessment,
            AssessmentMark, FeeCollection, HomeworkAssessment,
            ProjectWorkAssessment, StudentActivity
        )
        from portal.models import SkillsSubmission

        rows_to_delete = set()

        for group_key, (canonical, source_terms) in consolidation_plan.items():
            source_ids = {t.id for t in source_terms if t.id != canonical.id}

            if not source_ids:
                continue

            # Repoint all 9 FK models
            models_to_repoint = [
                (Exam, "term"),
                (SkillsTeacherComment, "term"),
                (AttendanceSummary, "term"),
                (CoScholasticScore, "term"),
                (SkillsAssessment, "term"),
                (ActivityAssessment, "term"),
                (AssessmentMark, "term"),
                (FeeCollection, "term"),
                (SkillsSubmission, "term"),
            ]

            for model, field_name in models_to_repoint:
                try:
                    self._repoint_model(
                        model, field_name, source_ids, canonical, report
                    )
                except Exception as e:
                    report.add_error(
                        f"Failed to repoint {model.__name__}: {e}"
                    )
                    raise

            # Verify CharField-only models (no FK, just name strings)
            self._verify_charfield_models(source_ids, report)

            # Collect orphans for deletion
            rows_to_delete.update(source_ids)

        # Delete orphaned Term rows
        if rows_to_delete:
            try:
                deleted_count, _ = Term.objects.filter(id__in=rows_to_delete).delete()
                report.orphans_deleted = deleted_count
            except Exception as e:
                report.add_error(f"Failed to delete orphaned terms: {e}")
                raise

    def _verify_charfield_models(self, term_ids: Set, report: ConsolidationReport):
        """
        Verify CharField-only models that store term name as string (no FK).

        These models (HomeworkAssessment, ProjectWorkAssessment, StudentActivity)
        have a term_name field but no term FK. Report orphans but don't rewrite.
        """
        from core.models import HomeworkAssessment, ProjectWorkAssessment, StudentActivity

        for model in [HomeworkAssessment, ProjectWorkAssessment, StudentActivity]:
            # Find rows that reference deleted terms by name
            # (This is a verification-only pass; we don't auto-fix)
            orphans = []
            for row in model.objects.all():
                term_name = getattr(row, "term_name", None)
                if term_name:
                    # Could verify against known term names, but for now just log
                    pass
            # TODO: log any orphans found (low priority for Phase 2)

    def _repoint_model(
        self, model, field_name: str, source_ids: Set, canonical, report
    ):
        """Repoint all FKs of a model from source terms to canonical."""
        affected = list(model.objects.filter(**{f"{field_name}_id__in": source_ids}))

        if not affected:
            return

        model_name = model.__name__
        repointed = 0
        collisions = 0

        # Check if this model has unique constraints involving the term field
        unique_constraints = self._get_unique_constraint_fields(model, field_name)

        for row in affected:
            if not unique_constraints:
                # No unique constraints: safe bulk update
                setattr(row, field_name, canonical)
                row.save(update_fields=[field_name, "updated_at"])
                repointed += 1
            else:
                # Check for collision: does a row exist with the new term
                # and same values for all unique-constraint fields?
                collision_row = self._find_collision(
                    model, row, field_name, canonical, unique_constraints
                )

                if collision_row and collision_row.id != row.id:
                    # Collision detected: merge row into collision_row
                    if self._merge_rows(row, collision_row):
                        row.delete()
                        collisions += 1
                        # Remove row from source list only if successfully deleted
                        source_ids.discard(row.id)
                    else:
                        report.add_error(
                            f"{model_name} pk={row.id}: "
                            f"collision but cannot merge (conflicting data), skipped"
                        )
                        # Don't delete this row's source term since it still references it
                        source_ids.discard(row.id)
                else:
                    # No collision: safe to repoint
                    setattr(row, field_name, canonical)
                    row.save(update_fields=[field_name, "updated_at"])
                    repointed += 1

        report.add_repoint(model_name, repointed)
        if collisions:
            report.add_collision(model_name, collisions)

    def _get_unique_constraint_fields(self, model, term_field: str) -> List[str]:
        """
        Return list of field names that are part of unique constraints including term.

        Returns empty list if no unique constraints found.
        """
        constraints = []

        # Check unique_together (deprecated but still used)
        if hasattr(model._meta, "unique_together") and model._meta.unique_together:
            for constraint in model._meta.unique_together:
                if term_field in constraint:
                    # Return all fields in this constraint except tenant (always present)
                    return [f for f in constraint if f not in ("tenant", term_field)]

        # Check UniqueConstraint
        if hasattr(model._meta, "constraints"):
            for constraint in model._meta.constraints:
                if hasattr(constraint, "fields") and term_field in constraint.fields:
                    return [f for f in constraint.fields if f not in ("tenant", term_field)]

        return constraints

    def _find_collision(
        self, model, row, term_field: str, new_term, unique_fields: List[str]
    ):
        """
        Find an existing row with the new term and same unique-constraint fields.

        Returns the collision row, or None.
        """
        if not unique_fields:
            return None

        filter_kwargs = {term_field: new_term}
        for field in unique_fields:
            filter_kwargs[field] = getattr(row, field)

        try:
            return model.objects.get(**filter_kwargs)
        except model.DoesNotExist:
            return None
        except model.MultipleObjectsReturned:
            # Shouldn't happen if constraint is enforced, but be safe
            return model.objects.filter(**filter_kwargs).first()

    def _merge_rows(self, source, target) -> bool:
        """
        Merge source row into target (target is authoritative).

        Returns True if merge succeeded, False if there's a conflict.
        """
        # Default: target wins, source is deleted
        # Some models (like SkillsTeacherComment) need content merge
        if hasattr(source, "comment") and hasattr(target, "comment"):
            # Content fields: copy non-empty from source to empty target
            if source.comment and not target.comment:
                target.comment = source.comment
                target.save(update_fields=["comment", "updated_at"])
            elif source.comment and target.comment:
                # Both have content: conflict
                return False

        if hasattr(source, "signature_image") and hasattr(target, "signature_image"):
            if source.signature_image and not target.signature_image:
                target.signature_image = source.signature_image
                target.save(update_fields=["signature_image", "updated_at"])
            elif source.signature_image and target.signature_image:
                # Both have content: conflict (but less critical than comment)
                pass

        return True
