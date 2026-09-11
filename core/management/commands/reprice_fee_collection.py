"""
One-off correction: re-price the FinanceFee charges of a single fee collection
that was generated with the wrong per-student amount.

For every FinanceFee under the given collection, this recomputes what the
student *should* owe using the exact same logic collection generation uses
today — the fee category's applicable FeeParticulars for that student
(applicability_rule + effective/expiry window) plus any active per-collection
extra particulars (FeeCollectionParticular) — and, when it differs from what
was billed, rewrites particular_total / balance, rebuilds the FinanceFeeItem
snapshot, and refreshes the guardian invoice.

Safety: only charges with nothing paid/discounted/fined against them yet
(balance == particular_total) are corrected. Anything already touched by a
payment is listed as NEEDS REVIEW and left alone.

Dry run by default. Pass --apply to write.

Usage:
    python manage.py reprice_fee_collection --tenant <id> --collection <uuid>
    python manage.py reprice_fee_collection --tenant <id> --collection <uuid> --apply
    python manage.py reprice_fee_collection --tenant <id> --collection <uuid> \
        --students BEG26009,BEG26011 --apply
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = "Re-price a fee collection's per-student charges to the correct amount."

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, required=True,
                            help='School / tenant ID that owns the collection')
        parser.add_argument('--collection', type=str, required=True,
                            help='FeeCollection UUID to re-price')
        parser.add_argument('--students', type=str, default='',
                            help='Optional comma-separated admission numbers or '
                                 'student UUIDs to limit the fix to')
        parser.add_argument('--apply', action='store_true',
                            help='Write the corrections (default: dry run)')

    def handle(self, *args, **options):
        try:
            school = School.objects.get(id=options['tenant'])
        except School.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant {options['tenant']} not found"))
            return

        apply = options['apply']
        if not apply:
            self.stdout.write(self.style.WARNING("DRY RUN — pass --apply to write changes\n"))

        with schema_context(school.schema_name):
            self._run(school, options['collection'],
                      [s.strip() for s in options['students'].split(',') if s.strip()],
                      apply)

    def _run(self, school, collection_id, student_filters, apply):
        from core.models import FinanceFee, FinanceFeeItem, FeeCollection
        from core.services.fee_collection_service import FeeCollectionService
        from core.services.invoice_service import InvoiceService
        from core.services.exceptions import ValidationException

        collection = FeeCollection.objects.filter(
            tenant=school, id=collection_id
        ).select_related('fee_category', 'academic_year').first()
        if not collection:
            self.stdout.write(self.style.ERROR(f"Collection {collection_id} not found for this tenant"))
            return

        self.stdout.write(f"Collection: {collection.name} "
                          f"({collection.fee_category.name}, "
                          f"{collection.academic_year.name if collection.academic_year else 'no year'})")

        fees = (
            FinanceFee.objects.filter(tenant=school, fee_collection=collection)
            .select_related('student', 'fee_category')
            .order_by('student__first_name', 'student__last_name')
        )
        if student_filters:
            fees = fees.filter(
                # admission_no OR id
                models_q(student_filters)
            )
        fees = list(fees)
        if not fees:
            self.stdout.write("  No matching FinanceFee rows.")
            return

        svc = FeeCollectionService(school)
        invoice_service = InvoiceService(school)

        checked = corrected = flagged = unchanged = 0

        for fee in fees:
            checked += 1
            name = fee.student.full_name
            try:
                base_total, applicable = svc._price_for_student(fee.fee_category, fee.student)
            except ValidationException as e:
                flagged += 1
                self.stdout.write(self.style.WARNING(
                    f"  SKIP {name}: cannot price ({e})"))
                continue

            extras = svc._collection_particular_lines(collection, fee.student)
            correct_total = base_total + sum((e.amount for e in extras), Decimal('0.00'))
            billed_total = fee.particular_total or Decimal('0.00')

            if correct_total == billed_total:
                unchanged += 1
                continue

            if fee.balance != billed_total:
                flagged += 1
                self.stdout.write(self.style.WARNING(
                    f"  NEEDS REVIEW {name}: billed {billed_total}, should be "
                    f"{correct_total}, but balance is {fee.balance} "
                    f"(payment/discount/fine already applied) — not touched"))
                continue

            corrected += 1
            self.stdout.write(self.style.SUCCESS(
                f"  FIX {name}: {billed_total} -> {correct_total}"))

            if not apply:
                continue

            with transaction.atomic():
                fee.particular_total = correct_total
                fee.balance = correct_total - (fee.discount_amount or Decimal('0.00'))
                fee.is_paid = fee.balance <= 0
                fee.save(update_fields=['particular_total', 'balance', 'is_paid', 'updated_at'])

                fee.items.all().delete()
                FinanceFeeItem.objects.bulk_create(
                    [FinanceFeeItem(
                        tenant=school, finance_fee=fee, fee_particular=p,
                        particular_name=p.name, amount=p.amount,
                    ) for p in applicable]
                    + [FinanceFeeItem(
                        tenant=school, finance_fee=fee, fee_particular=None,
                        particular_name=e.name, amount=e.amount,
                    ) for e in extras]
                )
                invoice_service.upsert_guardian_invoice(fee)

        self.stdout.write(
            f"\n  checked={checked} corrected={corrected} "
            f"needs_review={flagged} unchanged={unchanged}")
        if not apply and corrected:
            self.stdout.write(self.style.WARNING("  (dry run — re-run with --apply to write)"))


def models_q(values):
    """Q matching FinanceFee rows whose student is in `values` (admission_no or id)."""
    import uuid
    from django.db.models import Q
    admission_nos = []
    ids = []
    for v in values:
        try:
            ids.append(uuid.UUID(v))
        except (ValueError, AttributeError, TypeError):
            admission_nos.append(v)
    q = Q()
    if admission_nos:
        q |= Q(student__admission_no__in=admission_nos)
    if ids:
        q |= Q(student__id__in=ids)
    return q
