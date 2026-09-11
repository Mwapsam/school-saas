"""Generate next recurrence of recurring fee collections (Phase 6).

For each tenant, finds all recurring FeeCollections where next_generation_date <= today
and creates a draft recurrence for the next period. The new collection is left in draft
status (requires human publish) per the safe-by-default principle.

Idempotent: a given collection can be run multiple times without duplicating recurrences.
Suitable for Celery beat.

Usage:
    python manage.py generate_recurring_collections
    python manage.py generate_recurring_collections --tenant-id <school_id>
    python manage.py generate_recurring_collections --reference-date 2026-07-10
"""
from datetime import date

from django.core.management.base import BaseCommand

from core.models import School, FeeCollection
from core.services.fee_collection_service import FeeCollectionService


class Command(BaseCommand):
    help = "Generate next recurrence of recurring fee collections."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", help="Limit to a single School/tenant id")
        parser.add_argument("--reference-date", help="Date to check against (YYYY-MM-DD)")

    def handle(self, *args, **options):
        reference_date = date.today()
        if options.get("reference_date"):
            reference_date = date.fromisoformat(options["reference_date"])

        schools = School.objects.all()
        if options.get("tenant_id"):
            schools = schools.filter(id=options["tenant_id"])

        grand_total = 0
        for school in schools:
            svc = FeeCollectionService(school)

            # Find all recurring collections ready for next generation
            collections = FeeCollection.objects.filter(
                tenant=school,
                frequency__in=['monthly', 'termly', 'yearly'],
                next_generation_date__lte=reference_date,
            ).select_related('fee_category', 'batch', 'academic_year')

            tenant_generated = 0
            for collection in collections:
                try:
                    result = svc.generate_next_recurrence(collection.id)
                    tenant_generated += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  Generated: {result['next_recurrence'].name}"
                    ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"  Failed for {collection.name}: {e}"
                    ))

            if tenant_generated:
                grand_total += tenant_generated
                self.stdout.write(self.style.SUCCESS(
                    f"{school}: generated {tenant_generated} recurrence(s)"
                ))

        self.stdout.write(self.style.SUCCESS(f"Done. Total recurrences generated: {grand_total}"))
