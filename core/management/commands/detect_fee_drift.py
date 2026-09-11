"""Detect fee-ledger integrity drift (Phase 2).

Reports FinanceFee/FeeTransaction rows whose stored state is internally
inconsistent (negative balances, is_paid mismatches, orphan payments), per
tenant and optionally scoped to one academic year. Read-only — makes no changes.

Usage:
    python manage.py detect_fee_drift
    python manage.py detect_fee_drift --tenant-id <school_id>
    python manage.py detect_fee_drift --academic-year-id <ay_id>
"""
from django.core.management.base import BaseCommand

from core.models import School, AcademicYear
from core.services.finance_service import FinanceService


class Command(BaseCommand):
    help = "Detect fee-ledger integrity drift across tenants (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", help="Limit to a single School/tenant id")
        parser.add_argument("--academic-year-id", help="Limit to a single academic year id")

    def handle(self, *args, **options):
        schools = School.objects.all()
        if options.get("tenant_id"):
            schools = schools.filter(id=options["tenant_id"])

        total_anomalies = 0
        for school in schools:
            academic_year = None
            if options.get("academic_year_id"):
                academic_year = AcademicYear.objects.filter(
                    id=options["academic_year_id"], tenant=school
                ).first()
                if academic_year is None:
                    continue

            anomalies = FinanceService(school).find_balance_anomalies(academic_year=academic_year)
            if not anomalies:
                continue

            total_anomalies += len(anomalies)
            self.stdout.write(self.style.WARNING(
                f"\n{school} ({school.schema_name}): {len(anomalies)} anomaly(ies)"
            ))
            for a in anomalies:
                self.stdout.write(f"  - {a}")

        if total_anomalies == 0:
            self.stdout.write(self.style.SUCCESS("No fee-ledger drift detected."))
        else:
            self.stdout.write(self.style.ERROR(f"\nTotal anomalies: {total_anomalies}"))
