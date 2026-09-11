"""
Management command to reconcile FinanceFee charges that were priced before
FeeCollectionService started respecting FeeParticular.applicability_rule /
effective_date / expiry_date (see core/services/fee_collection_service.py
and core/services/fee_particulars.py::applicable_particulars_for_student).

Before that fix, every student in a batch was charged the sum of *all*
active particulars for the category, even ones scoped to other students -
e.g. a "Registration Fee" meant for one student got billed to their whole
batch. This command finds charges with no FinanceFeeItem snapshot (i.e.
priced by the old, unfiltered path) and re-evaluates what they should
actually owe.

Only charges with nothing paid/discounted against them yet (balance ==
particular_total) are corrected automatically - anything already partially
paid is flagged for manual review instead, since safely unwinding a payment
against a corrected total needs a human to look at it. Charges already
carrying FinanceFeeItem snapshots (priced by the corrected logic, or by the
older itemized publish_collection() path) are left alone entirely.

Separately, this reports any student who has more than one FinanceFee row for
the same (fee_category, academic_year) - caused by FeeCollectionService
creating a fresh charge under a differently-named collection instead of
recognising the student was already charged (fixed in
core/services/fee_collection_service.py; this command only cleans up data
created before that fix). By default duplicates are only reported, never
touched. Pass --merge-duplicates to actually merge them: a group is only
auto-merged when EVERY row in it still has balance == particular_total (i.e.
nothing paid/discounted/fined against any of them yet) - anything else is
left flagged for manual review, since safely unwinding a payment against a
corrected total needs a human to look at it.

Usage:
    python manage.py reconcile_collection_particulars --all [--dry-run]
    python manage.py reconcile_collection_particulars --tenant=<tenant_id> [--dry-run]
    python manage.py reconcile_collection_particulars --all --merge-duplicates --dry-run
    python manage.py reconcile_collection_particulars --all --merge-duplicates
"""
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = (
        "Reconcile FinanceFee charges priced before applicability-rule-aware "
        "collection pricing landed; flags anything unsafe to auto-correct."
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Tenant ID to fix')
        parser.add_argument('--all', action='store_true', help='Fix all tenants')
        parser.add_argument('--dry-run', action='store_true',
                             help='Show planned changes without writing')
        parser.add_argument('--merge-duplicates', action='store_true',
                             help='Also merge safe duplicate FinanceFee groups '
                                  '(no payment/discount/fine applied to any row)')

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
        merge_duplicates = options['merge_duplicates']
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written\n"))

        for tenant in tenants:
            self.stdout.write(f"\nTenant: {tenant.name}")
            with schema_context(tenant.schema_name):
                self.fix_tenant(tenant, dry_run, merge_duplicates)

        self.stdout.write(self.style.SUCCESS(
            "\nDone." if not dry_run else "\nDry run complete."))

    def fix_tenant(self, tenant, dry_run, merge_duplicates=False):
        from core.models import FinanceFee, FinanceFeeItem
        from core.services.fee_particulars import applicable_particulars_for_student
        from core.services.invoice_service import InvoiceService

        fees = (
            FinanceFee.objects.filter(tenant=tenant)
            .select_related('fee_category', 'student')
            .order_by('student_id', 'fee_category_id', 'academic_year_id')
        )
        if not fees:
            self.stdout.write("  No FinanceFee rows for this tenant.")
            return

        checked = corrected = flagged = 0
        invoice_service = InvoiceService(tenant)
        groups = defaultdict(list)

        for fee in fees:
            groups[(fee.student_id, fee.fee_category_id, fee.academic_year_id)].append(fee)

            if FinanceFeeItem.objects.filter(tenant=tenant, finance_fee=fee).exists():
                continue  # already itemized - priced by the corrected logic
            checked += 1

            applicable = applicable_particulars_for_student(fee.fee_category, fee.student)
            correct_total = sum((p.amount for p in applicable), Decimal('0.00'))
            if correct_total == fee.particular_total:
                continue  # already correct

            if fee.balance != fee.particular_total:
                flagged += 1
                self.stdout.write(
                    f"  NEEDS MANUAL REVIEW: FinanceFee {fee.id} ({fee.student.full_name}, "
                    f"'{fee.fee_category.name}') has a payment/discount already applied - "
                    f"billed={fee.particular_total}, correct={correct_total}, "
                    f"current balance={fee.balance}. Not touched."
                )
                continue

            corrected += 1
            self.stdout.write(
                f"  CORRECT: FinanceFee {fee.id} ({fee.student.full_name}, "
                f"'{fee.fee_category.name}'): {fee.particular_total} -> {correct_total}"
            )
            if not dry_run:
                fee.particular_total = correct_total
                fee.balance = correct_total - fee.discount_amount
                fee.save(update_fields=['particular_total', 'balance', 'updated_at'])
                FinanceFeeItem.objects.bulk_create([
                    FinanceFeeItem(
                        tenant=tenant, finance_fee=fee, fee_particular=p,
                        particular_name=p.name, amount=p.amount,
                    )
                    for p in applicable
                ])
                invoice_service.upsert_guardian_invoice(fee)

        duplicate_groups = merged_groups = duplicate_flagged = 0
        for (student_id, fee_category_id, academic_year_id), group in groups.items():
            if len(group) <= 1:
                continue
            duplicate_groups += 1
            student_name = group[0].student.full_name
            category_name = group[0].fee_category.name
            fee_ids = ', '.join(str(f.id) for f in group)

            if not merge_duplicates:
                self.stdout.write(
                    f"  DUPLICATE CHARGES (not modified): {student_name} has {len(group)} "
                    f"FinanceFee rows for '{category_name}' in the same academic year - {fee_ids}"
                )
                continue

            if any(f.balance != f.particular_total for f in group):
                duplicate_flagged += 1
                self.stdout.write(
                    f"  DUPLICATE NEEDS MANUAL REVIEW: {student_name} has {len(group)} "
                    f"FinanceFee rows for '{category_name}' and at least one already has a "
                    f"payment/discount/fine applied - {fee_ids}. Not merged."
                )
                continue

            merged_groups += 1
            self.stdout.write(
                f"  {'WOULD MERGE' if dry_run else 'MERGING'}: {student_name}'s {len(group)} "
                f"FinanceFee rows for '{category_name}' - {fee_ids}"
            )
            if not dry_run:
                self.merge_duplicate_group(tenant, group, invoice_service)

        self.stdout.write(
            f"  Charges checked: {checked}, corrected: {corrected}, "
            f"flagged for manual review: {flagged}, duplicate groups found: {duplicate_groups}, "
            f"duplicate groups merged: {merged_groups}, "
            f"duplicate groups flagged (has payments): {duplicate_flagged}"
        )

    def merge_duplicate_group(self, tenant, group, invoice_service):
        """Collapse a safe duplicate FinanceFee group (nothing paid/discounted/
        fined against any row) down to one correctly-priced row.

        Keeps the earliest-created row - this matches the selection order
        FinanceService._apply_fee_payment_effects already uses
        (.order_by('is_paid', 'created_at').first()), so this changes nothing
        about which row future payments would have settled against.

        FeeTransaction has no FK to FinanceFee (it resolves by student+
        category+year at lookup time), so no ledger rows need re-linking.
        FinanceFeeItem (CASCADE) and FamilyInvoiceLine (CASCADE, OneToOne)
        clean up automatically when the sibling rows are deleted.
        QuickBooksFeeInvoiceLineSync.finance_fee is SET_NULL, so a deleted
        duplicate's QB sync row survives orphaned - flagged below, not fixed
        here.
        """
        from core.models import FinanceFeeItem
        from core.services.fee_particulars import applicable_particulars_for_student

        with transaction.atomic():
            ordered = sorted(group, key=lambda f: f.created_at)
            kept = ordered[0]
            duplicates = ordered[1:]

            applicable = applicable_particulars_for_student(kept.fee_category, kept.student)
            correct_total = sum((p.amount for p in applicable), Decimal('0.00'))
            kept.particular_total = correct_total
            kept.balance = correct_total - kept.discount_amount
            kept.save(update_fields=['particular_total', 'balance', 'updated_at'])

            kept.items.all().delete()
            FinanceFeeItem.objects.bulk_create([
                FinanceFeeItem(
                    tenant=tenant, finance_fee=kept, fee_particular=p,
                    particular_name=p.name, amount=p.amount,
                )
                for p in applicable
            ])

            # qb_invoice_line_syncs is a reverse OneToOneField accessor - it
            # raises RelatedObjectDoesNotExist (not an empty manager) when no
            # sync row exists for this FinanceFee.
            orphaned_qb_lines = sum(
                1 for d in duplicates if hasattr(d, 'qb_invoice_line_syncs')
            )
            for dupe in duplicates:
                dupe.delete()

            invoice_service.upsert_guardian_invoice(kept)

            if orphaned_qb_lines:
                self.stdout.write(
                    f"    NOTE: {orphaned_qb_lines} QuickBooksFeeInvoiceLineSync row(s) "
                    f"orphaned by this merge (finance_fee set to null) - may need a manual "
                    f"QuickBooks re-sync, not handled by this command."
                )
