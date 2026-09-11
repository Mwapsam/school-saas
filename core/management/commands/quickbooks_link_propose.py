"""Propose links between existing QuickBooks records and Pinewood records.

Read-only. Writes three CSVs (customers / invoices / payments) with a blank
``decision`` column for a human to fill in with ``approve``, ``reject`` or
``manual:<qbo_id>``, then feed the reviewed file to ``quickbooks_link_apply``.

Run order matters: apply the customer links first, then re-run this for
invoices/payments (they can only match once their guardian's customer is linked).
"""
import csv
import os

from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = "Propose QuickBooks<->Pinewood links as reviewable CSVs (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant id, schema name, or domain")
        parser.add_argument("--academic-year", help="Limit invoices/payments to this year (by name)")
        parser.add_argument("--out-dir", default=".", help="Directory for the CSV files (default: cwd)")
        parser.add_argument("--min-score", type=float, default=0.85,
                            help="Score at/above which a customer match is labelled 'candidate'")
        parser.add_argument("--since", help="Only consider QBO records changed on/after this date (YYYY-MM-DD)")
        parser.add_argument("--window-days", type=int, default=21,
                            help="Date window (days) for invoice/payment matching")
        parser.add_argument("--kinds", default="customers,invoices,payments",
                            help="Comma list of which files to produce")

    def handle(self, *args, **options):
        tenant = self._resolve_tenant(options["tenant"])
        kinds = {k.strip() for k in options["kinds"].split(",") if k.strip()}
        out_dir = options["out_dir"]
        os.makedirs(out_dir, exist_ok=True)

        with schema_context(tenant.schema_name):
            from core.services.quickbooks_link_service import QuickBooksLinkService

            academic_year = None
            if options["academic_year"]:
                academic_year = self._resolve_academic_year(tenant, options["academic_year"])

            svc = QuickBooksLinkService(tenant)

            if "customers" in kinds:
                rows = svc.propose_customer_links(min_score=options["min_score"])
                self._write(out_dir, "customers.csv", rows)

            if "invoices" in kinds:
                rows = svc.propose_invoice_links(
                    academic_year=academic_year, window_days=options["window_days"],
                    since=options["since"])
                self._write(out_dir, "invoices.csv", rows)

            if "payments" in kinds:
                rows = svc.propose_payment_links(
                    academic_year=academic_year, window_days=options["window_days"],
                    since=options["since"])
                self._write(out_dir, "payments.csv", rows)

    def _write(self, out_dir, name, rows):
        path = os.path.join(out_dir, name)
        if not rows:
            self.stdout.write(self.style.WARNING(f"{name}: nothing to propose"))
            # still write an empty file with no header rather than crash
            open(path, "w").close()
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        strong = sum(1 for r in rows if r.get("score", 0) >= 0.85)
        self.stdout.write(self.style.SUCCESS(
            f"{name}: {len(rows)} rows ({strong} at score >= 0.85) -> {path}"))

    def _resolve_tenant(self, identifier: str) -> School:
        for lookup in ("id", "schema_name", "domains__domain"):
            try:
                return School.objects.get(**{lookup: identifier})
            except (School.DoesNotExist, ValueError):
                continue
        raise CommandError(f"Tenant not found: {identifier}")

    def _resolve_academic_year(self, tenant, name: str):
        from core.models import AcademicYear
        with schema_context(tenant.schema_name):
            ay = AcademicYear.objects.filter(tenant=tenant, name=name).first()
        if ay is None:
            raise CommandError(f"Academic year not found: {name}")
        return ay
