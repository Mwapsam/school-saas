import json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = (
        "Reconcile a tenant's local fee ledger against its QuickBooks mirror. "
        "Read-only: reports invoices/payments that never synced, balance "
        "mismatches, and sync rows whose QuickBooks record has gone missing. "
        "Use as the post-cutover verification gate and the ongoing drift check."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant", required=True,
            help="Tenant id, schema name, or domain",
        )
        parser.add_argument(
            "--academic-year",
            help="Limit to this academic year (by name, e.g. '2024-2025')",
        )
        parser.add_argument(
            "--invoices", action="store_true",
            help="Run invoice reconciliation (default: run both if neither flag given)",
        )
        parser.add_argument(
            "--payments", action="store_true",
            help="Run payment reconciliation (default: run both if neither flag given)",
        )
        parser.add_argument(
            "--since",
            help="For payment reconciliation, the start date (YYYY-MM-DD). "
                 "Defaults to the last 30 days.",
        )
        parser.add_argument(
            "--relink-unapplied", action="store_true",
            help="Attach invoices to payments that synced as unapplied credits "
                 "(writes to QuickBooks and the local balance)",
        )
        parser.add_argument(
            "--json", action="store_true", dest="as_json",
            help="Emit raw JSON instead of a formatted summary",
        )

    def handle(self, *args, **options):
        tenant = self._resolve_tenant(options["tenant"])
        run_invoices = options["invoices"] or not options["payments"]
        run_payments = options["payments"] or not options["invoices"]

        with schema_context(tenant.schema_name):
            from core.services.quickbooks_fee_sync_service import QuickBooksFeeSync

            academic_year = None
            if options["academic_year"]:
                academic_year = self._resolve_academic_year(tenant, options["academic_year"])

            sync = QuickBooksFeeSync(tenant)
            report = {"tenant": tenant.name, "schema": tenant.schema_name}

            if options["relink_unapplied"]:
                report["relink_unapplied"] = sync.relink_unapplied_payments(
                    academic_year=academic_year
                )

            if run_invoices:
                report["invoices"] = sync.reconcile_invoices(academic_year=academic_year)
            if run_payments:
                start_date = None
                if options["since"]:
                    try:
                        start_date = timezone.make_aware(
                            datetime.strptime(options["since"], "%Y-%m-%d")
                        )
                    except ValueError:
                        raise CommandError("--since must be YYYY-MM-DD")
                report["payments"] = sync.reconcile_payments(
                    start_date=start_date, academic_year=academic_year
                )

        if options["as_json"]:
            self.stdout.write(json.dumps(report, indent=2, default=str))
            return

        self._print_report(report)

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

    def _print_report(self, report: dict):
        self.stdout.write(self.style.HTTP_INFO(
            f"QuickBooks reconciliation - {report['tenant']} ({report['schema']})"
        ))
        if "relink_unapplied" in report:
            r = report["relink_unapplied"]
            self.stdout.write(self.style.MIGRATE_HEADING("RELINK UNAPPLIED PAYMENTS"))
            self.stdout.write(
                f"  relinked={r['relinked']} skipped={r['skipped']} "
                f"errors={r['error_count']}"
            )
            for e in r.get("errors", [])[:50]:
                self.stdout.write(self.style.WARNING(f"    - {e}"))
        for section in ("invoices", "payments"):
            data = report.get(section)
            if data is None:
                continue
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING(section.upper()))
            count = data.get("discrepancy_count", 0)
            style = self.style.SUCCESS if count == 0 else self.style.WARNING
            self.stdout.write(style(f"  {data.get('summary', '')} ({count} discrepancies)"))
            for key, value in data.items():
                if key in ("discrepancies", "summary", "discrepancy_count"):
                    continue
                self.stdout.write(f"  {key}: {value}")
            for d in data.get("discrepancies", [])[:50]:
                self.stdout.write(self.style.WARNING(f"    - {d}"))
            extra = len(data.get("discrepancies", [])) - 50
            if extra > 0:
                self.stdout.write(f"    ... and {extra} more")
