"""Phase 5 — year-scoped financial reporting.

Every report is scoped to a single AcademicYear (and optionally a batch/class) so
figures never mix years. Reads are derived from the FinanceFee charges and the
FeeTransaction ledger. A small CSV helper turns any row list into export text.
"""
import csv
import io
import itertools
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from django.core.exceptions import ValidationError
from django.db.models import Sum, Q, Case, When, Value, DecimalField
from django.db.models.functions import TruncMonth, TruncDate

from core.models import (
    AcademicYear, FinanceFee, FeeParticular, FeeTransaction, FinanceTransaction, Student, Batch,
    BatchStudent, FeeCollection, StudentGuardianRelation,
)
from core.services.exceptions import NotFoundException
from core.services.fee_particulars import (
    get_finance_fee_particulars, applicable_particulars_for_student,
)

# FinanceTransaction rows for fee payments always use this category name (see
# FinanceService._get_or_create_payment_category) - excluded from the Day
# Book's general-ledger side so a fee payment is never counted twice (it's
# already fully represented via FeeTransaction, which also covers itemized
# payments that don't create a FinanceTransaction row at all).
FEE_PAYMENTS_CATEGORY_NAME = "Fee Payments"

# Ledger transaction types that increase vs decrease what a student owes.
_DEBIT_TYPES = ("adjustment", "fine")          # charges, carry-forward, fines
_CREDIT_TYPES = ("payment", "discount", "refund")


def _sum(qs, field="amount") -> Decimal:
    return qs.aggregate(total=Sum(field))['total'] or Decimal('0.00')


def _reversal_hidden_ids(rows) -> set:
    """IDs of FeeTransaction rows that are reversal noise and must not appear on
    statements/receipts: every ``REVERSAL:<payment_id>`` refund row and the
    original payment row it cancels. The two net to zero, so hiding both keeps
    every printed total correct."""
    hidden = set()
    reversed_payment_ids = set()
    for t in rows:
        ref = t.reference_number or ''
        if t.transaction_type == 'refund' and ref.startswith('REVERSAL:'):
            hidden.add(t.id)
            reversed_payment_ids.add(ref.split(':', 1)[1].strip())
    for t in rows:
        if t.transaction_type == 'payment' and str(t.id) in reversed_payment_ids:
            hidden.add(t.id)
    return hidden


class FeeReportingService:
    def __init__(self, tenant):
        self.tenant = tenant

    # ------------------------------------------------------------------ #
    # Guardian lookup
    # ------------------------------------------------------------------ #
    def resolve_guardian_name(self, student) -> Optional[str]:
        """Father's/Guardian's name for receipts and statements: prefer the
        student's designated immediate contact, else the first linked
        guardian."""
        info = self.resolve_guardian_display(student)
        return info['name'] if info else None

    def resolve_guardian_display(self, student) -> Optional[Dict[str, str]]:
        """{'name', 'relation', 'label'} for the parent shown on a receipt.

        Picks the primary contact: the StudentGuardianRelation flagged
        is_immediate_contact, else the student's immediate_contact guardian,
        else the first linked guardian. ``label`` is the relationship rendered
        for print - "Father" / "Mother" when known, otherwise "Guardian".
        """
        rel = (
            StudentGuardianRelation.objects.filter(
                tenant=self.tenant, student=student, is_immediate_contact=True,
            ).select_related('guardian').first()
            or StudentGuardianRelation.objects.filter(
                tenant=self.tenant, student=student,
            ).select_related('guardian').first()
        )
        guardian = rel.guardian if rel else getattr(student, 'immediate_contact', None)
        if guardian is None:
            return None

        raw = (getattr(rel, 'relation', '') or getattr(guardian, 'relation', '') or '').strip()
        key = raw.lower()
        if key in ('father', 'dad'):
            label = 'Father'
        elif key in ('mother', 'mum', 'mom'):
            label = 'Mother'
        elif raw:
            label = raw.title()
        else:
            label = 'Guardian'
        return {
            'name': f"{guardian.first_name} {guardian.last_name}".strip(),
            'relation': raw,
            'label': label,
        }

    # ------------------------------------------------------------------ #
    # Student statement
    # ------------------------------------------------------------------ #
    def student_statement(self, student, academic_year: AcademicYear,
                          exclude_unpublished_collections: bool = False) -> Dict[str, Any]:
        """Opening + charges + payments + discounts/fines + closing for one year.

        exclude_unpublished_collections: when True, charges belonging to a
        still-draft FeeCollection are left out of current_outstanding - used
        by the parent portal, which must never show a charge before staff
        have explicitly published its collection's invoices. Staff-facing
        callers leave this False so they see everything, published or not.
        """
        ledger = FeeTransaction.objects.filter(
            tenant=self.tenant, student=student, academic_year=academic_year,
        ).select_related('fee_category').order_by('transaction_date')

        ledger_rows = list(ledger)
        hidden_ids = _reversal_hidden_ids(ledger_rows)
        visible_rows = [t for t in ledger_rows if t.id not in hidden_ids]

        line_items: List[Dict[str, Any]] = []
        for t in visible_rows:
            is_debit = t.transaction_type in _DEBIT_TYPES
            line_items.append({
                'date': t.transaction_date,
                'type': t.transaction_type,
                'description': t.description or '',
                'fee_category': t.fee_category.name if t.fee_category else '',
                'debit': t.amount if is_debit else Decimal('0.00'),
                'credit': t.amount if not is_debit else Decimal('0.00'),
            })

        # Real charges, sourced from FinanceFee/FinanceFeeItem directly -
        # ordinary charge creation (FeeCollectionService) never writes an
        # 'adjustment' ledger row, so the FeeTransaction-only view above
        # would otherwise show no charges/particulars at all. Every
        # FinanceFee is included (not just balance__gt=0) so fully-settled
        # charges still appear on the statement. Uses the same
        # get_finance_fee_particulars() helper as the guardian invoice PDF,
        # so both surfaces render identical names/amounts for the same charge.
        charges_qs = FinanceFee.objects.filter(
            tenant=self.tenant, student=student, academic_year=academic_year,
        ).select_related('fee_category', 'fee_collection')
        if exclude_unpublished_collections:
            charges_qs = charges_qs.exclude(fee_collection__status='draft')
        charges = [
            {
                'fee_category': fee.fee_category.name,
                'fee_collection': fee.fee_collection.name if fee.fee_collection_id else None,
                'particulars': get_finance_fee_particulars(fee),
                'particular_total': fee.particular_total,
                'discount_amount': fee.discount_amount or Decimal('0.00'),
                'balance': fee.balance,
                'is_paid': fee.is_paid,
            }
            for fee in charges_qs.order_by('created_at')
        ]

        # Fines bump FinanceFee.balance without touching particular_total, so
        # they're added on top of the charges total here. The 'adjustment'
        # ledger sum is deliberately NOT added: it's empty for ordinary
        # collection-created charges, and the two flows that do write it
        # (record_student_fee, carry_forward_student) also set
        # particular_total to the same amount - adding both would double-count.
        def _vsum(ttype):
            return sum((t.amount for t in visible_rows if t.transaction_type == ttype),
                       Decimal('0.00'))

        total_charged = _sum(charges_qs, field='particular_total') + _vsum('fine')
        total_paid = _vsum('payment')
        total_discounts = _vsum('discount')
        total_refunds = _vsum('refund')

        current_outstanding = _sum(charges_qs, field='balance')

        return {
            'student_id': str(student.id),
            'student_name': f"{student.first_name} {student.last_name}",
            'admission_no': getattr(student, 'admission_no', ''),
            'academic_year': academic_year.name,
            'charges': charges,
            'line_items': line_items,
            'total_charged': total_charged,
            'total_paid': total_paid,
            'total_discounts': total_discounts,
            'total_refunds': total_refunds,
            'current_outstanding': current_outstanding,
        }

    # ------------------------------------------------------------------ #
    # Single-collection receipt (Particulars / Summary / Payment History)
    # ------------------------------------------------------------------ #
    def student_collection_receipt(self, student, fee_collection: FeeCollection) -> Dict[str, Any]:
        """One FinanceFee's particulars, totals, and payment history for a
        single fee collection - the shape a printable receipt needs, as
        opposed to student_statement()'s flat whole-year ledger.

        Payments/fines can't be joined to fee_collection directly -
        FeeTransaction has no fee_collection/finance_fee FK - so they're
        attributed via the fee category's particular ids (snapshotted on
        FinanceFeeItem rows when the collection was published, or the fee
        category's current active FeeParticulars otherwise - the same set
        used to price/allocate payments elsewhere in this layer)."""
        finance_fee = FinanceFee.objects.filter(
            tenant=self.tenant, student=student, fee_collection=fee_collection,
        ).select_related('batch__course').first()
        if not finance_fee:
            raise NotFoundException(
                "No charges found for this student in this fee collection",
                details={'student_id': str(student.id), 'fee_collection_id': str(fee_collection.id)},
            )

        items = list(finance_fee.items.all())
        if items:
            # Itemized snapshot — every line the student was actually billed,
            # including any per-collection extra particular (e.g. PTA), which
            # is stored as an item with fee_particular=None.
            particulars = [
                {'name': i.particular_name, 'amount': i.amount}
                for i in sorted(items, key=lambda i: i.amount, reverse=True)
            ]
            particular_ids = [i.fee_particular_id for i in items if i.fee_particular_id]
        else:
            # No FinanceFeeItem snapshot — fall back to the fee category's
            # active particulars for this student, PLUS this collection's own
            # extra particulars, so the breakdown still adds up to the charge.
            applicable = applicable_particulars_for_student(
                finance_fee.fee_category, student,
            )
            extras = list(fee_collection.extra_particulars.filter(is_active=True))
            particulars = [
                {'name': p.name, 'amount': p.amount}
                for p in sorted(applicable, key=lambda p: p.amount, reverse=True)
            ] + [
                {'name': e.name, 'amount': e.amount} for e in extras
            ]
            particular_ids = [p.id for p in applicable]

        total_particular_fees = finance_fee.particular_total or Decimal('0.00')
        total_discount = finance_fee.discount_amount or Decimal('0.00')

        ledger = FeeTransaction.objects.filter(
            tenant=self.tenant, student=student, academic_year=fee_collection.academic_year,
        ).filter(
            Q(fee_particular_id__in=particular_ids)
            | Q(fee_category=finance_fee.fee_category, fee_particular__isnull=True)
        )
        # Scope fines to this collection's term window so a fine raised for a
        # different term's collection of the same category doesn't leak in.
        fine_rows = ledger.filter(transaction_type='fine')
        if fee_collection.start_date and fee_collection.end_date:
            fine_rows = fine_rows.filter(
                transaction_date__date__gte=fee_collection.start_date,
                transaction_date__date__lte=fee_collection.end_date,
            )
        total_fine = _sum(fine_rows)

        payment_rows = list(
            ledger.filter(transaction_type='payment')
            .select_related('collected_by', 'fee_particular', 'fee_category')
            .order_by('transaction_date')
        )
        # Drop payments that were later reversed - reverse_payment() writes a
        # REVERSAL:<payment_id> refund row and restores the balance, so the
        # payment must not show on the receipt's history either.
        reversed_ids = {
            (ref or '').split(':', 1)[1].strip()
            for ref in ledger.filter(
                transaction_type='refund',
                reference_number__startswith='REVERSAL:',
            ).values_list('reference_number', flat=True)
        }
        if reversed_ids:
            payment_rows = [t for t in payment_rows if str(t.id) not in reversed_ids]

        def _receipt_no(t):
            return t.reference_number or f"RCPT-{str(t.id)[:8].upper()}"

        def _particular_name(t):
            if t.fee_particular:
                return t.fee_particular.name
            if t.fee_category:
                return t.fee_category.name
            return 'General Payment'

        # Rows from one payment submission share a receipt number and are
        # written back-to-back within the same atomic call, so grouping
        # consecutive rows by receipt number reassembles each receipt without
        # needing a dedicated grouping table.
        payment_history = []
        for receipt_no, rows in itertools.groupby(payment_rows, key=_receipt_no):
            rows = list(rows)
            first = rows[0]
            payment_history.append({
                'receipt_no': receipt_no,
                'date': first.transaction_date,
                'mode': first.get_payment_method_display(),
                'notes': first.description or '',
                'cashier': first.collected_by.full_name if first.collected_by else None,
                'amount': sum((r.amount for r in rows), Decimal('0.00')),
                'lines': [{'name': _particular_name(r), 'amount': r.amount} for r in rows],
            })

        total_fees = total_particular_fees - total_discount + total_fine
        payment_done = max(total_fees - finance_fee.balance, Decimal('0.00'))

        return {
            'student_name': student.full_name,
            'admission_no': getattr(student, 'admission_no', ''),
            'class_name': finance_fee.batch.course.course_name if finance_fee.batch and finance_fee.batch.course else '',
            'batch_name': finance_fee.batch.name if finance_fee.batch else '',
            'fee_collection_name': fee_collection.name,
            'invoice_number': finance_fee.invoice_number,
            'particulars': particulars,
            'total_particular_fees': total_particular_fees,
            'total_discount': total_discount,
            'total_fine': total_fine,
            'total_fees': total_fees,
            'payment_done': payment_done,
            'amount_to_pay': finance_fee.balance,
            'payment_history': payment_history,
        }

    # ------------------------------------------------------------------ #
    # Which collection did a payment actually apply to?
    # ------------------------------------------------------------------ #
    def collection_for_payment(self, student, reference_number: str) -> Optional[FeeCollection]:
        """Resolve the FeeCollection a payment settled, from the payment's own
        ledger rows — not from whatever collection a caller happens to pass in.

        The Collect Fees page shows the whole year's ledger regardless of the
        collection dropdown, so a print link built from that dropdown can name
        the wrong term. This walks the payment's FeeTransaction rows back to
        the FinanceFee (and therefore FeeCollection) they were tagged against.
        """
        rows = list(FeeTransaction.objects.filter(
            tenant=self.tenant, student=student,
            reference_number=reference_number, transaction_type='payment',
        ).values('academic_year_id', 'fee_category_id', 'fee_particular_id', 'transaction_date'))

        def _pick(candidates, pay_date):
            candidates = [c for c in candidates if c.fee_collection_id]
            if not candidates:
                return None
            # Prefer a collection whose term window contains the payment date -
            # disambiguates two same-category collections in the same year
            # (termly billing that reuses the same particular each term).
            if pay_date is not None:
                d = pay_date.date() if hasattr(pay_date, 'date') else pay_date
                for c in candidates:
                    col = c.fee_collection
                    if col.start_date and col.end_date and col.start_date <= d <= col.end_date:
                        return col
            return candidates[0].fee_collection

        for r in rows:
            base = FinanceFee.objects.filter(
                tenant=self.tenant, student=student,
                academic_year_id=r['academic_year_id'],
                fee_collection__isnull=False,
            ).select_related('fee_collection').order_by('created_at')
            if r['fee_particular_id']:
                hit = _pick(list(base.filter(items__fee_particular_id=r['fee_particular_id'])),
                            r['transaction_date'])
                if hit:
                    return hit
            hit = _pick(list(base.filter(fee_category_id=r['fee_category_id'])),
                        r['transaction_date'])
            if hit:
                return hit
        return None

    # ------------------------------------------------------------------ #
    # Single-payment receipt, by reference number (no FeeCollection needed)
    # ------------------------------------------------------------------ #
    def receipt_by_reference(self, reference_number: str, student_ids=None) -> Optional[Dict[str, Any]]:
        """A payment receipt built directly from the FeeTransaction rows
        sharing ``reference_number`` - these already carry everything a
        receipt needs (category/particular, amount, payment method,
        cashier), so unlike student_collection_receipt() no FeeCollection
        lookup is required. Used by the parent portal, where a payment isn't
        naturally scoped to one collection from the caller's point of view.

        ``student_ids``, when given, scopes (and thereby authorizes) the
        query to a specific set of students - e.g. one guardian's own
        children. Returns None if no matching payment rows are found, which
        callers should treat as "not found" (whether because the reference
        number doesn't exist, or it belongs to someone else's payment).
        """
        q = Q(tenant=self.tenant, reference_number=reference_number, transaction_type='payment')
        if student_ids is not None:
            q &= Q(student_id__in=student_ids)
        rows = list(
            FeeTransaction.objects.filter(q)
            .select_related('student', 'collected_by', 'fee_particular', 'fee_category')
            .order_by('transaction_date')
        )
        if not rows:
            return None

        def _particular_name(t):
            if t.fee_particular:
                return t.fee_particular.name
            if t.fee_category:
                return t.fee_category.name
            return 'General Payment'

        first = rows[0]
        return {
            'reference_number': reference_number,
            'student_name': first.student.full_name,
            'admission_no': getattr(first.student, 'admission_no', ''),
            'date': first.transaction_date,
            'mode': first.get_payment_method_display(),
            'notes': first.description or '',
            'cashier': first.collected_by.full_name if first.collected_by else None,
            'amount': sum((r.amount for r in rows), Decimal('0.00')),
            'lines': [{'name': _particular_name(r), 'amount': r.amount} for r in rows],
        }

    # ------------------------------------------------------------------ #
    # Outstanding balance report
    # ------------------------------------------------------------------ #
    def outstanding_balance_report(self, academic_year: AcademicYear, batch: Batch = None) -> List[Dict[str, Any]]:
        q = Q(tenant=self.tenant, academic_year=academic_year, balance__gt=0)
        if batch is not None:
            q &= Q(student__student_batches__batch=batch)

        rows = (
            FinanceFee.objects.filter(q)
            .values('student_id', 'student__first_name', 'student__last_name', 'student__admission_no')
            .annotate(outstanding=Sum('balance'))
            .order_by('-outstanding')
        )
        return [{
            'student_id': str(r['student_id']),
            'student_name': f"{r['student__first_name']} {r['student__last_name']}",
            'admission_no': r['student__admission_no'],
            'outstanding': r['outstanding'] or Decimal('0.00'),
        } for r in rows]

    # ------------------------------------------------------------------ #
    # Payment summary (by method)
    # ------------------------------------------------------------------ #
    def payment_summary(self, academic_year: AcademicYear, start_date=None, end_date=None) -> Dict[str, Any]:
        q = Q(tenant=self.tenant, academic_year=academic_year, transaction_type='payment')
        if start_date:
            q &= Q(transaction_date__gte=start_date)
        if end_date:
            q &= Q(transaction_date__lte=end_date)

        payments = FeeTransaction.objects.filter(q)
        by_method = (
            payments.values('payment_method')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        return {
            'academic_year': academic_year.name,
            'total_collected': _sum(payments),
            'by_method': [
                {'payment_method': m['payment_method'] or 'unknown', 'total': m['total'] or Decimal('0.00')}
                for m in by_method
            ],
        }

    # ------------------------------------------------------------------ #
    # Academic-year institutional summary
    # ------------------------------------------------------------------ #
    def academic_year_summary(self, academic_year: AcademicYear) -> Dict[str, Any]:
        ledger = FeeTransaction.objects.filter(tenant=self.tenant, academic_year=academic_year)
        fees = FinanceFee.objects.filter(tenant=self.tenant, academic_year=academic_year)
        return {
            'academic_year': academic_year.name,
            'total_charged': _sum(ledger.filter(transaction_type='adjustment')) + _sum(ledger.filter(transaction_type='fine')),
            'total_collected': _sum(ledger.filter(transaction_type='payment')),
            'total_discounts': _sum(ledger.filter(transaction_type='discount')),
            'total_fines': _sum(ledger.filter(transaction_type='fine')),
            'total_outstanding': _sum(fees, field='balance'),
            'students_with_charges': fees.values('student_id').distinct().count(),
            'students_outstanding': fees.filter(balance__gt=0).values('student_id').distinct().count(),
        }

    # ------------------------------------------------------------------ #
    # Class / grade-based report
    # ------------------------------------------------------------------ #
    def class_based_report(self, academic_year: AcademicYear) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        batches = Batch.objects.filter(
            tenant=self.tenant, academic_year=academic_year, is_deleted=False,
        ).select_related('course')

        for batch in batches:
            student_ids = BatchStudent.objects.filter(
                tenant=self.tenant, batch=batch, is_active=True,
            ).values_list('student_id', flat=True)

            fees = FinanceFee.objects.filter(
                tenant=self.tenant, academic_year=academic_year, student_id__in=student_ids,
            )
            payments = FeeTransaction.objects.filter(
                tenant=self.tenant, academic_year=academic_year,
                transaction_type='payment', student_id__in=student_ids,
            )
            rows.append({
                'batch': batch.name,
                'grade': batch.course.course_name if batch.course else '',
                'students': len(student_ids),
                'collected': _sum(payments),
                'outstanding': _sum(fees, field='balance'),
            })
        return rows

    # ------------------------------------------------------------------ #
    # Fee statistics (Fedena-style aggregates for charting)
    # ------------------------------------------------------------------ #
    def fee_statistics(self, academic_year: AcademicYear) -> Dict[str, Any]:
        """Monthly collection trend + category breakdown for one academic year."""
        payments = FeeTransaction.objects.filter(
            tenant=self.tenant, academic_year=academic_year, transaction_type='payment',
        )

        monthly = (
            payments.annotate(month=TruncMonth('transaction_date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )
        by_category = (
            payments.values('fee_category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        outstanding = _sum(
            FinanceFee.objects.filter(tenant=self.tenant, academic_year=academic_year),
            field='balance',
        )

        return {
            'academic_year': academic_year.name,
            'total_collected': _sum(payments),
            'total_outstanding': outstanding,
            'monthly': [
                {'month': m['month'], 'total': m['total'] or Decimal('0.00')}
                for m in monthly
            ],
            'by_category': [
                {'fee_category': c['fee_category__name'] or 'Unknown', 'total': c['total'] or Decimal('0.00')}
                for c in by_category
            ],
        }

    # ------------------------------------------------------------------ #
    # Day Book (cash/bank reconciliation across all money flows)
    # ------------------------------------------------------------------ #
    def day_book(self, date_from: date, date_to: date, academic_year: AcademicYear = None) -> Dict[str, Any]:
        """Per-day, per-payment-mode cash reconciliation spanning both fee
        collection and the general ledger (payroll, donations, etc).

        Fee cash-in/out is read entirely from FeeTransaction (the single
        primitive that covers both the legacy single-category payment path
        and itemized multi-particular payments). The general-ledger side
        reads FinanceTransaction but excludes the "Fee Payments" category to
        avoid double-counting, since every fee payment already has a
        FeeTransaction row but only the legacy path also has a mirrored
        FinanceTransaction row.

        Calendar-date scoped, not academic-year scoped by default (Day Book
        is a cash ledger, not a per-year statement) - academic_year narrows
        the fee side only, when supplied.
        """
        # FeeTransaction.transaction_date is a DateTimeField (auto_now_add), so
        # it's bucketed via a TruncDate annotation - grouping on the raw field
        # would key each row by its exact timestamp instead of the calendar day.
        fee_q = Q(tenant=self.tenant, transaction_date__date__gte=date_from, transaction_date__date__lte=date_to)
        if academic_year is not None:
            fee_q &= Q(academic_year=academic_year)

        fee_in = FeeTransaction.objects.filter(fee_q, transaction_type='payment')
        fee_out = FeeTransaction.objects.filter(fee_q, transaction_type__in=('refund',))

        general_q = Q(
            tenant=self.tenant, transaction_date__gte=date_from, transaction_date__lte=date_to,
        ) & ~Q(category__name=FEE_PAYMENTS_CATEGORY_NAME)
        general = FinanceTransaction.objects.filter(general_q).select_related('category')

        by_date_mode: Dict[date, Dict[str, Dict[str, Decimal]]] = {}

        def _bucket(day, mode):
            return (
                by_date_mode.setdefault(day, {})
                .setdefault(mode or 'other', {'in': Decimal('0.00'), 'out': Decimal('0.00')})
            )

        fee_in = fee_in.annotate(day=TruncDate('transaction_date'))
        fee_out = fee_out.annotate(day=TruncDate('transaction_date'))

        for row in fee_in.values('day', 'payment_method').annotate(total=Sum('amount')):
            _bucket(row['day'], row['payment_method'])['in'] += row['total'] or Decimal('0.00')

        for row in fee_out.values('day', 'payment_method').annotate(total=Sum('amount')):
            _bucket(row['day'], row['payment_method'])['out'] += row['total'] or Decimal('0.00')

        for row in general.values('transaction_date', 'payment_method', 'category__is_income').annotate(total=Sum('amount')):
            bucket = _bucket(row['transaction_date'], row['payment_method'])
            key = 'in' if row['category__is_income'] else 'out'
            bucket[key] += row['total'] or Decimal('0.00')

        days = []
        running_balance = Decimal('0.00')
        cursor = date_from
        while cursor <= date_to:
            modes = by_date_mode.get(cursor, {})
            total_in = sum((m['in'] for m in modes.values()), Decimal('0.00'))
            total_out = sum((m['out'] for m in modes.values()), Decimal('0.00'))
            opening = running_balance
            closing = opening + total_in - total_out
            days.append({
                'date': cursor,
                'opening_balance': opening,
                'total_in': total_in,
                'total_out': total_out,
                'closing_balance': closing,
                'by_mode': modes,
            })
            running_balance = closing
            cursor += timedelta(days=1)

        return {
            'date_from': date_from,
            'date_to': date_to,
            'days': days,
            'total_in': sum((d['total_in'] for d in days), Decimal('0.00')),
            'total_out': sum((d['total_out'] for d in days), Decimal('0.00')),
            'closing_balance': days[-1]['closing_balance'] if days else Decimal('0.00'),
        }

    # ------------------------------------------------------------------ #
    # Particular-wise Student Transaction Report (per-student reconciliation)
    # ------------------------------------------------------------------ #
    def filtered_students_for_ledger_report(self, student_status='active', class_filter='all',
                                              batch_filter='all', academic_year: AcademicYear = None):
        """Students matching the report's status/class/batch filters, ordered
        by name. Mirrors the legacy view's ``_get_filtered_students``: a
        ``class_filter`` (course id) takes precedence over ``batch_filter``
        when both are supplied."""
        students_query = Student.objects.filter(tenant=self.tenant)

        if student_status == 'active':
            students_query = students_query.filter(is_deleted=False)

        if class_filter != 'all':
            try:
                course_batches_query = Batch.objects.filter(tenant=self.tenant, course_id=class_filter)
                if academic_year:
                    course_batches_query = course_batches_query.filter(academic_year=academic_year)
                course_batches = course_batches_query.values_list('id', flat=True)
                student_ids = BatchStudent.objects.filter(
                    tenant=self.tenant, batch_id__in=course_batches
                ).values_list('student_id', flat=True)
                students_query = students_query.filter(id__in=student_ids)
            except (ValueError, ValidationError) as e:
                logger.debug("Invalid class_filter %r: %s", class_filter, e)

        elif batch_filter != 'all':
            try:
                batch_query = Batch.objects.filter(tenant=self.tenant, id=batch_filter)
                if academic_year:
                    batch_query = batch_query.filter(academic_year=academic_year)
                student_ids = BatchStudent.objects.filter(
                    tenant=self.tenant, batch_id__in=batch_query.values_list('id', flat=True)
                ).values_list('student_id', flat=True)
                students_query = students_query.filter(id__in=student_ids)
            except (ValueError, ValidationError) as e:
                logger.debug("Invalid batch_filter %r: %s", batch_filter, e)

        return students_query.order_by('first_name', 'last_name')

    def _ledger_aggregates(self, academic_year: AcademicYear, student_ids, fee_account,
                            from_date_obj=None, to_date_obj=None) -> Dict[str, Dict[str, Decimal]]:
        """One grouped query: student_id -> dict of charged/paid/credited totals, split PTA vs not."""
        if not student_ids:
            return {}

        decimal_field = DecimalField(max_digits=15, decimal_places=2)

        ledger = FeeTransaction.objects.filter(
            tenant=self.tenant, academic_year=academic_year, student_id__in=student_ids,
        )
        if fee_account != 'all':
            try:
                ledger = ledger.filter(fee_category_id=fee_account)
            except (ValueError, ValidationError) as e:
                logger.debug("Invalid fee_account filter %r: %s", fee_account, e)
        if from_date_obj:
            ledger = ledger.filter(transaction_date__date__gte=from_date_obj)
        if to_date_obj:
            ledger = ledger.filter(transaction_date__date__lte=to_date_obj)

        pta_q = Q(fee_category__name__icontains='PTA')

        def total_case(extra_q=None, types=None, single_type=None):
            condition = Q(transaction_type=single_type) if single_type else Q(transaction_type__in=types)
            if extra_q is not None:
                condition &= extra_q
            return Sum(Case(When(condition, then='amount'), default=Value(0), output_field=decimal_field))

        rows = ledger.values('student_id').annotate(
            charged=total_case(types=_DEBIT_TYPES),
            paid=total_case(single_type='payment'),
            credited=total_case(types=_CREDIT_TYPES),
            pta_charged=total_case(extra_q=pta_q, types=_DEBIT_TYPES),
            pta_paid=total_case(extra_q=pta_q, single_type='payment'),
            pta_credited=total_case(extra_q=pta_q, types=_CREDIT_TYPES),
        )

        zero = Decimal('0.00')
        result = {}
        for row in rows:
            result[row['student_id']] = {
                'charged': row['charged'] or zero,
                'paid': row['paid'] or zero,
                'credited': row['credited'] or zero,
                'pta_charged': row['pta_charged'] or zero,
                'pta_paid': row['pta_paid'] or zero,
                'pta_credited': row['pta_credited'] or zero,
            }
        return result

    def student_ledger_rows(self, academic_year: AcademicYear, students, fee_account='all',
                             from_date_obj=None, to_date_obj=None) -> List[Dict[str, Any]]:
        """Per-student expected/paid/balance, split into PTA vs tuition, for the
        given queryset/list of students. Identical math to the legacy
        ``ParticularWiseStudentTransactionReportView._build_rows``."""
        students = list(students)
        student_ids = [s.id for s in students]

        aggregates = self._ledger_aggregates(academic_year, student_ids, fee_account, from_date_obj, to_date_obj)

        batch_names = {}
        for bs in BatchStudent.objects.filter(tenant=self.tenant, student_id__in=student_ids).select_related('batch'):
            batch_names.setdefault(bs.student_id, bs.batch.name)

        zero = Decimal('0.00')
        rows = []
        for student in students:
            agg = aggregates.get(student.id, {
                'charged': zero, 'paid': zero, 'credited': zero,
                'pta_charged': zero, 'pta_paid': zero, 'pta_credited': zero,
            })
            tuition_charged = agg['charged'] - agg['pta_charged']
            tuition_paid = agg['paid'] - agg['pta_paid']
            tuition_credited = agg['credited'] - agg['pta_credited']

            rows.append({
                'student_id': str(student.id),
                'student_name': f"{student.first_name} {student.last_name}".strip(),
                'batch_name': batch_names.get(student.id, "Not Assigned"),
                'expected_amount': agg['charged'],
                'paid_amount': agg['paid'],
                'balance_amount': agg['charged'] - agg['credited'],
                'pta_expected': agg['pta_charged'],
                'pta_paid': agg['pta_paid'],
                'pta_balance': agg['pta_charged'] - agg['pta_credited'],
                'tuition_expected': tuition_charged,
                'tuition_paid': tuition_paid,
                'tuition_balance': tuition_charged - tuition_credited,
            })
        return rows

    @staticmethod
    def student_ledger_grand_totals(rows: List[Dict[str, Any]]) -> Dict[str, Decimal]:
        zero = Decimal('0.00')
        totals = {
            'grand_expected': zero, 'grand_paid': zero, 'grand_balance': zero,
            'grand_pta_expected': zero, 'grand_pta_paid': zero, 'grand_pta_balance': zero,
            'grand_tuition_expected': zero, 'grand_tuition_paid': zero, 'grand_tuition_balance': zero,
        }
        for row in rows:
            totals['grand_expected'] += row['expected_amount']
            totals['grand_paid'] += row['paid_amount']
            totals['grand_balance'] += row['balance_amount']
            totals['grand_pta_expected'] += row['pta_expected']
            totals['grand_pta_paid'] += row['pta_paid']
            totals['grand_pta_balance'] += row['pta_balance']
            totals['grand_tuition_expected'] += row['tuition_expected']
            totals['grand_tuition_paid'] += row['tuition_paid']
            totals['grand_tuition_balance'] += row['tuition_balance']
        return totals

    def student_ledger_report(self, academic_year: AcademicYear, student_status='active',
                               class_filter='all', batch_filter='all', fee_account='all',
                               from_date_obj=None, to_date_obj=None) -> Dict[str, Any]:
        """Full particular-wise student transaction report: filtered students,
        per-student rows and grand totals, in one call."""
        students = self.filtered_students_for_ledger_report(
            student_status=student_status, class_filter=class_filter,
            batch_filter=batch_filter, academic_year=academic_year,
        )
        rows = self.student_ledger_rows(academic_year, students, fee_account, from_date_obj, to_date_obj)
        grand_totals = self.student_ledger_grand_totals(rows)
        return {'rows': rows, 'grand_totals': grand_totals}

    @staticmethod
    def student_ledger_csv(rows: List[Dict[str, Any]], grand_totals: Dict[str, Decimal],
                            with_expected: bool) -> str:
        """Renders the student ledger report to CSV text, identical columns to
        the legacy view's ``_render_csv``."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        header = ['Sl No.', 'Student Name', 'Batch Name(s)', 'Expected Amount', 'Paid Amount', 'Balance Amount']
        if with_expected:
            header += [
                'PTA Expected', 'PTA Paid', 'PTA Balance',
                'Tuition Expected', 'Tuition Paid', 'Tuition Balance',
            ]
        writer.writerow(header)

        for i, row in enumerate(rows, 1):
            line = [
                i, row['student_name'], row['batch_name'],
                row['expected_amount'], row['paid_amount'], row['balance_amount'],
            ]
            if with_expected:
                line += [
                    row['pta_expected'], row['pta_paid'], row['pta_balance'],
                    row['tuition_expected'], row['tuition_paid'], row['tuition_balance'],
                ]
            writer.writerow(line)

        total_line = ['', 'Grand Total', '', grand_totals['grand_expected'], grand_totals['grand_paid'], grand_totals['grand_balance']]
        if with_expected:
            total_line += [
                grand_totals['grand_pta_expected'], grand_totals['grand_pta_paid'], grand_totals['grand_pta_balance'],
                grand_totals['grand_tuition_expected'], grand_totals['grand_tuition_paid'], grand_totals['grand_tuition_balance'],
            ]
        writer.writerow(total_line)
        return buf.getvalue()

    # ------------------------------------------------------------------ #
    # CSV export helper
    # ------------------------------------------------------------------ #
    @staticmethod
    def to_csv(rows: List[Dict[str, Any]], fieldnames: List[str] = None) -> str:
        if not rows:
            return ""
        fieldnames = fieldnames or list(rows[0].keys())
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, '') for k in fieldnames})
        return buf.getvalue()
