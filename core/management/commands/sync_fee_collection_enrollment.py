"""Backfill FinanceFee obligations for students already enrolled in a batch
against that batch's already-open FeeCollection(s).

Why this is needed: FeeCollectionService.sync_student_enrollment() is invoked
automatically by the post_save(BatchStudent) signal (core/signals.py) for
enrollments created the normal way. But some enrollment paths never fire that
signal — bulk_create() doesn't call save()/emit post_save, and the Fedena
data migration inserted batch_student rows via raw SQL. Students enrolled
through either path show up on /batches/ (raw BatchStudent count) but are
silently missing from /finance/collections/ (FinanceFee-based obligation
count) for any collection opened before or without their enrollment being
synced. This command reconciles that drift; it is safe to re-run (sync_
student_enrollment skips students who already have a FinanceFee for a given
collection).

Only the ACTIVE academic year's enrollments are considered. BatchStudent.
is_active alone is not a reliable "currently enrolled" signal: Batch is
year-specific, and a student promoted through several years accumulates one
is_active=True BatchStudent row per year (see promote_students.py's
deactivation fix). Scoping to batch__academic_year=<active year> keeps this
command's counts meaningful and avoids syncing obligations against stale
collections tied to old batches.

Usage:
    python manage.py sync_fee_collection_enrollment
    python manage.py sync_fee_collection_enrollment --tenant-id <school_id>
    python manage.py sync_fee_collection_enrollment --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import School, BatchStudent
from core.services.fee_collection_service import FeeCollectionService


class Command(BaseCommand):
    help = "Backfill FinanceFee obligations for already-enrolled students against open fee collections."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", help="Limit to a single School/tenant id")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be created without writing anything",
        )

    def handle(self, *args, **options):
        schools = School.objects.all()
        if options.get("tenant_id"):
            schools = schools.filter(id=options["tenant_id"])

        dry_run = options["dry_run"]
        grand_total_created = 0

        for school in schools:
            svc = FeeCollectionService(school)
            active_year = svc.get_active_academic_year()
            if not active_year:
                continue

            enrollments = BatchStudent.objects.filter(
                tenant=school, is_active=True, student__is_active=True, student__is_deleted=False,
                batch__academic_year=active_year,
            ).select_related('student', 'batch')

            if not enrollments.exists():
                continue

            created = 0
            checked = 0

            with transaction.atomic():
                for enrollment in enrollments:
                    checked += 1
                    created += svc.sync_student_enrollment(enrollment.batch, enrollment.student)
                if dry_run:
                    transaction.set_rollback(True)

            if created:
                verb = "Would create" if dry_run else "Created"
                self.stdout.write(self.style.SUCCESS(
                    f"{school} ({school.schema_name}): checked {checked} enrollment(s), "
                    f"{verb} {created} FinanceFee obligation(s)"
                ))
                grand_total_created += created
            else:
                self.stdout.write(f"{school} ({school.schema_name}): checked {checked} enrollment(s), no drift found")

        if grand_total_created == 0:
            self.stdout.write(self.style.SUCCESS("\nNo drift found — all collections already reflect current enrollment."))
        else:
            verb = "would be created" if dry_run else "created"
            self.stdout.write(self.style.WARNING(f"\nTotal: {grand_total_created} obligation(s) {verb} across all tenants."))
