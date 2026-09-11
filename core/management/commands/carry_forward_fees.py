"""Carry forward outstanding balances between academic years (Phase 4).

Usage:
    python manage.py carry_forward_fees --tenant-id <school_id> \
        --from-year <ay_id> --to-year <ay_id>

Idempotent: re-running does not duplicate carried balances.
"""
from django.core.management.base import BaseCommand, CommandError

from core.models import School, AcademicYear
from core.services.fee_reconciliation_service import FeeReconciliationService


class Command(BaseCommand):
    help = "Carry forward outstanding student balances from one academic year to the next."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", required=True, help="School/tenant id")
        parser.add_argument("--from-year", required=True, help="Source AcademicYear id")
        parser.add_argument("--to-year", required=True, help="Target AcademicYear id")

    def handle(self, *args, **options):
        try:
            school = School.objects.get(id=options["tenant_id"])
        except School.DoesNotExist:
            raise CommandError("Tenant not found")

        from_year = AcademicYear.objects.filter(id=options["from_year"], tenant=school).first()
        to_year = AcademicYear.objects.filter(id=options["to_year"], tenant=school).first()
        if not from_year or not to_year:
            raise CommandError("from-year/to-year not found for this tenant")

        result = FeeReconciliationService(school).carry_forward_year(from_year, to_year)
        self.stdout.write(self.style.SUCCESS(
            f"Carried forward {result['total_carried']} across "
            f"{result['students_processed']} student(s): "
            f"{result['from_year']} -> {result['to_year']}"
        ))
