"""
Recompute FinanceFee.balance from the ledger, for cases where it has drifted
out of sync with the actual charges/payments (e.g. a payment reversal that
restored more than the payment had removed).

For each FinanceFee in scope:

    correct_balance = particular_total
                    + sum(fine  ledger rows)
                    - sum(discount ledger rows)
                    - ( sum(payment rows) - sum(refund rows) )      # net cash
    correct_balance = max(correct_balance, 0)                        # no negative

Ledger rows are matched on (student, fee_category, academic_year) - the same
scope payments are recorded against. On this tenant each term has its own fee
category, so that scope is one term / one collection; double-check before using
on a tenant that reuses a category across terms.

Dry run by default. Pass --apply to write balance / is_paid and refresh the
guardian invoice.

Usage:
    python manage.py recompute_fee_balance --tenant 1 --students BEG26009
    python manage.py recompute_fee_balance --tenant 1 --collection <uuid> --students BEG26009 --apply
    python manage.py recompute_fee_balance --tenant 1 --collection <uuid> --apply
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django_tenants.utils import schema_context

from core.models import School


def _q(values):
    import uuid
    from django.db.models import Q
    adm, ids = [], []
    for v in values:
        try:
            ids.append(uuid.UUID(v))
        except (ValueError, AttributeError, TypeError):
            adm.append(v)
    q = Q()
    if adm:
        q |= Q(student__admission_no__in=adm)
    if ids:
        q |= Q(student__id__in=ids)
    return q


class Command(BaseCommand):
    help = "Recompute FinanceFee.balance from the ledger where it has drifted."

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, required=True,
                            help='School id or schema_name')
        parser.add_argument('--collection', type=str, default='',
                            help='Limit to one FeeCollection UUID')
        parser.add_argument('--students', type=str, default='',
                            help='Comma-separated admission numbers or student UUIDs')
        parser.add_argument('--apply', action='store_true',
                            help='Write the corrections (default: dry run)')

    def handle(self, *args, **options):
        ident = options['tenant']
        school = (School.objects.filter(id=ident).first() if ident.isdigit() else None) \
            or School.objects.filter(schema_name=ident).first()
        if not school:
            self.stdout.write(self.style.ERROR(f"Tenant '{ident}' not found"))
            return

        if not options['apply']:
            self.stdout.write(self.style.WARNING("DRY RUN - pass --apply to write changes\n"))

        with schema_context(school.schema_name):
            self._run(
                school,
                options['collection'].strip(),
                [s.strip() for s in options['students'].split(',') if s.strip()],
                options['apply'],
            )

    def _run(self, school, collection_id, student_filters, apply):
        from core.models import FinanceFee, FeeTransaction
        from core.services.invoice_service import InvoiceService

        fees = (
            FinanceFee.objects.filter(tenant=school)
            .select_related('student', 'fee_category', 'fee_collection')
            .order_by('student__first_name', 'student__last_name')
        )
        if collection_id:
            fees = fees.filter(fee_collection_id=collection_id)
        if student_filters:
            fees = fees.filter(_q(student_filters))
        fees = list(fees)
        if not fees:
            self.stdout.write("  No matching FinanceFee rows.")
            return

        invoice_service = InvoiceService(school)
        checked = fixed = ok = 0

        for fee in fees:
            checked += 1
            ledger = FeeTransaction.objects.filter(
                tenant=school, student=fee.student,
                fee_category=fee.fee_category, academic_year=fee.academic_year,
            )

            def _s(ttype):
                return ledger.filter(transaction_type=ttype).aggregate(
                    t=Sum('amount'))['t'] or Decimal('0.00')

            charge = fee.particular_total or Decimal('0.00')
            fines = _s('fine')
            discounts = _s('discount')
            net_paid = _s('payment') - _s('refund')

            correct = charge + fines - discounts - net_paid
            if correct < 0:
                correct = Decimal('0.00')

            name = fee.student.full_name
            coll = fee.fee_collection.name if fee.fee_collection_id else '(no collection)'

            if correct == fee.balance:
                ok += 1
                continue

            fixed += 1
            self.stdout.write(self.style.SUCCESS(
                f"  FIX {name} / {coll}: balance {fee.balance} -> {correct}"
                f"   (charge={charge} fines={fines} discounts={discounts} net_paid={net_paid})"))

            if not apply:
                continue

            with transaction.atomic():
                fee.balance = correct
                fee.is_paid = correct <= 0
                fee.save(update_fields=['balance', 'is_paid', 'updated_at'])
                invoice_service.upsert_guardian_invoice(fee)

        self.stdout.write(f"\n  checked={checked}  fixed={fixed}  already_ok={ok}")
        if not apply and fixed:
            self.stdout.write(self.style.WARNING("  (dry run - re-run with --apply to write)"))
