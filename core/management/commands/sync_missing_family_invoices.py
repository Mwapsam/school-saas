"""
Management command to catch up FinanceFee charges from published fee
collections that never got a FamilyInvoiceLine — and so never showed up in
FamilyInvoice, the parent portal, or the admin parent detail page.

This happened whenever InvoiceService.upsert_guardian_invoice() ran against a
student with no ``Student.immediate_contact`` set, even though the student
had a guardian linked via StudentGuardianRelation (e.g. added through the
"Add Parent" form without ticking "primary contact"). It silently skipped
billing instead of raising, so a published collection could generate charges
that were never invoiced to anyone. InvoiceService now falls back to the
guardian on file in that case (and backfills immediate_contact) - this
command re-runs the upsert for every charge that predates that fix.

Usage:
    python manage.py sync_missing_family_invoices --all [--dry-run]
    python manage.py sync_missing_family_invoices --tenant=<tenant_id> [--dry-run]
"""
from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = (
        "Generate FamilyInvoice/FamilyInvoiceLine rows for published-collection "
        "charges that were silently skipped because the student had no billing "
        "guardian resolved at publish time."
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
        from core.models import FamilyInvoiceLine, FinanceFee
        from core.services.invoice_service import InvoiceService

        invoiced_ids = FamilyInvoiceLine.objects.filter(tenant=tenant).values_list(
            'finance_fee_id', flat=True
        )
        orphaned = (
            FinanceFee.objects.filter(tenant=tenant, fee_collection__status='published')
            .exclude(id__in=list(invoiced_ids))
            .select_related('student', 'fee_collection', 'academic_year')
        )

        if not orphaned:
            self.stdout.write("  No un-invoiced published charges for this tenant.")
            return

        invoice_service = InvoiceService(tenant)
        synced = skipped = 0

        for finance_fee in orphaned:
            student = finance_fee.student
            self.stdout.write(
                f"  {student.admission_no} — {finance_fee.fee_collection.name} "
                f"({finance_fee.balance})"
            )
            if dry_run:
                continue
            invoice = invoice_service.upsert_guardian_invoice(finance_fee)
            if invoice is not None:
                synced += 1
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"    skipped — {student.admission_no} still has no guardian on file"
                ))

        self.stdout.write(
            f"  Charges checked: {len(orphaned)}, synced: "
            f"{synced if not dry_run else '(skipped in dry-run)'}, "
            f"still unbillable: {skipped if not dry_run else '?'}"
        )
