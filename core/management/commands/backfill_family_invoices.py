"""
Management command to backfill existing FamilyInvoice/FamilyInvoiceLine rows
created before two fixes landed in InvoiceService:

  - FamilyInvoiceLine.description used to be just the fee category's name
    (e.g. "Term 2 Tuition Fee"); it's now the itemized particular breakdown
    (e.g. "Registration Fee, Tuition Fee"), via
    core.services.fee_particulars.describe_finance_fee().
  - FamilyInvoice.due_date used to never be set; it's now derived from the
    earliest due_date among the invoice's collection-sourced charges, via
    InvoiceService.recompute_totals().

Both of those only apply going forward - a line's description is written
once at creation and never rewritten, and due_date is only recomputed when
recompute_totals() runs again (a new charge or payment). This command
catches up everything created before those fixes landed. Line ``amount`` is
never touched here - it's an immutable snapshot of the charge as billed.

Usage:
    python manage.py backfill_family_invoices --all [--dry-run]
    python manage.py backfill_family_invoices --tenant=<tenant_id> [--dry-run]
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = (
        "Backfill FamilyInvoiceLine.description (itemized particulars) and "
        "FamilyInvoice.due_date for invoices created before those fixes."
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Tenant ID to fix')
        parser.add_argument('--all', action='store_true', help='Fix all tenants')
        parser.add_argument('--dry-run', action='store_true',
                             help='Show planned changes without writing')

    def handle(self, *args, **options):
        if options['all']:
            tenants = list(School.objects.exclude(schema_name='public'))
        elif options['tenant']:
            try:
                tenants = [School.objects.get(id=options['tenant'])]
            except School.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"Tenant with ID {options['tenant']} not found"))
                return
        else:
            self.stdout.write(self.style.ERROR("Please specify --tenant=<id> or --all"))
            return

        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written\n"))

        for tenant in tenants:
            self.stdout.write(f"\nTenant: {tenant.name}")
            with schema_context(tenant.schema_name):
                self.fix_tenant(tenant, dry_run)

        self.stdout.write(self.style.SUCCESS(
            "\nDone." if not dry_run else "\nDry run complete."))

    def fix_tenant(self, tenant, dry_run):
        from core.models import FamilyInvoiceLine
        from core.services.fee_particulars import describe_finance_fee
        from core.services.invoice_service import InvoiceService

        lines = (
            FamilyInvoiceLine.objects.filter(tenant=tenant)
            .select_related('finance_fee__fee_category', 'invoice')
        )
        if not lines:
            self.stdout.write("  No FamilyInvoiceLine rows for this tenant.")
            return

        checked = updated = 0
        invoice_ids = set()

        for line in lines:
            checked += 1
            invoice_ids.add(line.invoice_id)
            new_description = describe_finance_fee(line.finance_fee)
            if new_description == line.description:
                continue
            updated += 1
            self.stdout.write(
                f"  UPDATE line {line.id}: '{line.description}' -> '{new_description}'"
            )
            if not dry_run:
                line.description = new_description
                line.save(update_fields=['description', 'updated_at'])

        invoice_service = InvoiceService(tenant)
        resynced = 0
        if not dry_run:
            from core.models import FamilyInvoice
            for invoice in FamilyInvoice.objects.filter(tenant=tenant, id__in=invoice_ids):
                invoice_service.recompute_totals(invoice)
                resynced += 1

        self.stdout.write(
            f"  Lines checked: {checked}, updated: {updated}, "
            f"invoices resynced (totals/due_date): {resynced if not dry_run else '(skipped in dry-run)'}"
        )
