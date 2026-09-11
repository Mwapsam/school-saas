"""Accrue late fees on overdue fee collections (Phase 3).

For each tenant, applies every active FineSlab to the overdue, unpaid charges of
each active FeeCollection (matched by the collection's due_date and academic
year). Idempotent: a given (student, category, year, fine_slab) is fined at most
once. Suitable for Celery beat.

Usage:
    python manage.py accrue_late_fines
    python manage.py accrue_late_fines --tenant-id <school_id>
    python manage.py accrue_late_fines --reference-date 2025-03-01   # for testing
"""
from datetime import date

from django.core.management.base import BaseCommand

from core.models import School, FineSlab, FeeCollection
from core.services.finance_service import FinanceService


class Command(BaseCommand):
    help = "Apply late fines to overdue fee collections across tenants."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", help="Limit to a single School/tenant id")
        parser.add_argument("--reference-date", help="Date to evaluate overdue against (YYYY-MM-DD)")

    def handle(self, *args, **options):
        reference_date = date.today()
        if options.get("reference_date"):
            reference_date = date.fromisoformat(options["reference_date"])

        schools = School.objects.all()
        if options.get("tenant_id"):
            schools = schools.filter(id=options["tenant_id"])

        grand_total = 0
        for school in schools:
            svc = FinanceService(school)
            slabs = list(FineSlab.objects.filter(tenant=school, is_active=True))
            if not slabs:
                continue

            collections = FeeCollection.objects.filter(
                tenant=school, is_active=True
            ).select_related('fee_category', 'academic_year')

            tenant_applied = 0
            for collection in collections:
                if not collection.due_date:
                    continue
                for slab in slabs:
                    result = svc.accrue_late_fines(
                        slab, collection.fee_category, collection.due_date,
                        academic_year=collection.academic_year,
                        reference_date=reference_date,
                    )
                    tenant_applied += result["applied"]

            if tenant_applied:
                grand_total += tenant_applied
                self.stdout.write(self.style.SUCCESS(
                    f"{school}: applied fines to {tenant_applied} charge(s)"
                ))

        self.stdout.write(self.style.SUCCESS(f"Done. Total fines applied: {grand_total}"))
