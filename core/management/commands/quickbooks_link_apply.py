"""Apply a reviewed link CSV from ``quickbooks_link_propose``.

For each row whose ``decision`` is ``approve`` (or ``manual:<qbo_id>``) writes
the matching QuickBooks*Sync row as ``synced`` with the QuickBooks id, so the
normal forward-only sync updates that record instead of creating a duplicate.
Idempotent - re-running skips rows already linked. Always dry-run first.
"""
import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = "Apply a reviewed QuickBooks<->Pinewood link CSV."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant id, schema name, or domain")
        parser.add_argument("--file", required=True, help="Reviewed CSV from quickbooks_link_propose")
        parser.add_argument("--kind", required=True, choices=["customers", "invoices", "payments"])
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would be linked without writing")

    def handle(self, *args, **options):
        tenant = self._resolve_tenant(options["tenant"])
        try:
            with open(options["file"], newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        except FileNotFoundError:
            raise CommandError(f"File not found: {options['file']}")

        if not rows:
            self.stdout.write(self.style.WARNING("No rows in file; nothing to do"))
            return

        kind = options["kind"]
        dry_run = options["dry_run"]

        with schema_context(tenant.schema_name):
            from core.services.quickbooks_link_service import QuickBooksLinkService
            svc = QuickBooksLinkService(tenant)
            apply_fn = {
                "customers": svc.apply_customer_links,
                "invoices": svc.apply_invoice_links,
                "payments": svc.apply_payment_links,
            }[kind]

            if dry_run:
                result = apply_fn(rows, dry_run=True)
            else:
                with transaction.atomic():
                    result = apply_fn(rows, dry_run=False)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{kind}: linked={result.get('linked', 0)} "
            f"skipped={result.get('skipped', 0)} "
            f"needs_review={result.get('needs_review', 0)} "
            f"errors={len(result.get('errors', []))}"))
        for err in result.get("errors", [])[:100]:
            self.stdout.write(self.style.WARNING(f"  - {err}"))

    def _resolve_tenant(self, identifier: str) -> School:
        for lookup in ("id", "schema_name", "domains__domain"):
            try:
                return School.objects.get(**{lookup: identifier})
            except (School.DoesNotExist, ValueError):
                continue
        raise CommandError(f"Tenant not found: {identifier}")
