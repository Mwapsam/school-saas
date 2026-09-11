"""Guardian-level consolidated invoicing.

FamilyInvoice/FamilyInvoiceLine are the local source of truth for "one
invoice per guardian per academic year, one line per child's charge" -
independent of QuickBooks, so balances and PDF downloads never depend on QB
reachability. QuickBooksFeeSync (core/services/quickbooks_fee_sync_service.py)
mirrors this local state to QuickBooks asynchronously.
"""
from decimal import Decimal
from typing import Optional

from django.db import transaction

from core.models import AcademicYear, FamilyInvoice, FamilyInvoiceLine, FinanceFee, Student, StudentGuardianRelation
from core.services.fee_particulars import describe_finance_fee, get_finance_fee_particulars

from .base import TenantAwareService


class InvoiceService(TenantAwareService[FamilyInvoice]):
    def __init__(self, tenant):
        super().__init__(FamilyInvoice, tenant)

    def _resolve_billing_guardian(self, student: Student):
        """Who a student's charges should be invoiced to.

        Prefers ``Student.immediate_contact``, but that FK can be null even
        when the student has a guardian on file — e.g. a guardian linked
        through the "Add Parent" form without ticking "primary contact".
        Falling back silently skipped invoicing entirely (see
        ``upsert_guardian_invoice``'s old None-guardian bail-out), so a
        published collection could generate zero invoices for a family that
        does have a guardian. Fall back to the relation flagged primary, then
        to the oldest linked guardian, and backfill ``immediate_contact`` so
        the rest of the app (which reads that FK directly) sees the same
        answer from here on.
        """
        if student.immediate_contact_id is not None:
            return student.immediate_contact

        relation = (
            StudentGuardianRelation.objects.filter(
                tenant=self.tenant, student=student, is_immediate_contact=True
            )
            .select_related("guardian")
            .first()
        ) or (
            StudentGuardianRelation.objects.filter(tenant=self.tenant, student=student)
            .select_related("guardian")
            .order_by("created_at")
            .first()
        )
        if relation is None:
            return None

        student.immediate_contact = relation.guardian
        student.save(update_fields=["immediate_contact"])
        return relation.guardian

    def _next_invoice_number(self, academic_year: AcademicYear) -> str:
        count = FamilyInvoice.objects.filter(
            tenant=self.tenant, academic_year=academic_year
        ).count()
        return f"INV-{str(self.tenant.id)[:8]}-{str(academic_year.id)[:8]}-{count + 1:06d}"

    def recompute_totals(self, invoice: FamilyInvoice) -> FamilyInvoice:
        """Recompute subtotal/paid/balance/status from the invoice's lines.

        ``line.amount`` is an immutable snapshot of the charge at billing
        time (the subtotal). ``FinanceFee.balance`` is the live outstanding
        amount for that charge - it already nets out payments, discounts,
        fines and reversals (FinanceService is the only writer of balance),
        so balance_due is simply the live sum of each line's FinanceFee
        balance, and amount_paid is derived as subtotal - balance_due.
        Never hand-edit these fields elsewhere.
        """
        lines = list(invoice.lines.select_related('finance_fee__fee_collection').all())
        subtotal = sum((l.amount for l in lines), Decimal('0.00'))
        balance_due = sum(
            (l.finance_fee.balance for l in lines if l.finance_fee is not None),
            Decimal('0.00'),
        )
        amount_paid = subtotal - balance_due

        # The earliest due date among the invoice's collection-sourced
        # charges, re-derived from current lines every time so a newly
        # added, earlier-due collection always pulls the date forward.
        # Ad-hoc lines (no fee_collection) don't have a due date to offer.
        collection_due_dates = [
            l.finance_fee.fee_collection.due_date
            for l in lines
            if l.finance_fee is not None and l.finance_fee.fee_collection_id
        ]

        invoice.subtotal = subtotal
        invoice.total_amount = subtotal
        invoice.amount_paid = amount_paid
        invoice.balance_due = balance_due
        invoice.status = 'paid' if balance_due <= 0 and subtotal > 0 else 'open'
        if collection_due_dates:
            invoice.due_date = min(collection_due_dates)
        invoice.save(update_fields=[
            'subtotal', 'total_amount', 'amount_paid', 'balance_due', 'status',
            'due_date', 'last_updated_at',
        ])
        return invoice

    @transaction.atomic
    def upsert_guardian_invoice(self, finance_fee: FinanceFee) -> Optional[FamilyInvoice]:
        """Get-or-create the guardian's consolidated invoice for this charge's
        academic year, and get-or-create the line mirroring this charge.

        Returns None (and logs) when the student has no guardian on file at
        all (see ``_resolve_billing_guardian``) - the charge still stands
        locally, it's simply not billed to a guardian yet.
        """
        student = finance_fee.student
        guardian = self._resolve_billing_guardian(student)
        academic_year = finance_fee.academic_year
        if guardian is None or academic_year is None:
            import logging
            logging.getLogger('finance').warning(
                "Skipping guardian invoice upsert for FinanceFee %s: missing "
                "immediate_contact guardian or academic_year", finance_fee.id,
            )
            return None

        invoice, _ = FamilyInvoice.objects.get_or_create(
            tenant=self.tenant, guardian=guardian, academic_year=academic_year,
            defaults={'invoice_number': self._next_invoice_number(academic_year)},
        )

        FamilyInvoiceLine.objects.get_or_create(
            tenant=self.tenant, finance_fee=finance_fee,
            defaults={
                'invoice': invoice,
                'student': student,
                'academic_year': academic_year,
                'description': describe_finance_fee(finance_fee),
                'amount': finance_fee.balance,
            },
        )

        return self.recompute_totals(invoice)

    def mark_invoice_paid_if_settled(self, finance_fee: FinanceFee) -> Optional[FamilyInvoice]:
        """Recompute the invoice a payment/refund against ``finance_fee``
        belongs to. No-op if the charge has no invoice line yet.
        """
        line = FamilyInvoiceLine.objects.filter(
            tenant=self.tenant, finance_fee=finance_fee
        ).select_related('invoice').first()
        if line is None:
            return None
        return self.recompute_totals(line.invoice)


def build_invoice_pdf_context(invoice: FamilyInvoice) -> dict:
    """Shared render context for the invoice PDF template, used by both the
    staff Django view and the parent-portal DRF view so the two PDFs stay
    identical in layout.
    """
    from collections import OrderedDict
    from core.models import CurrencyConfiguration

    currency = CurrencyConfiguration.get_active_currency(invoice.tenant)

    def fmt(amount):
        return currency.format_amount(amount) if currency else f"{amount:.2f}"

    students_grouped: "OrderedDict" = OrderedDict()
    lines = invoice.lines.select_related('student', 'finance_fee__batch').order_by('student_id', 'created_at')
    for line in lines:
        student = line.student
        key = str(student.id)
        if key not in students_grouped:
            batch = line.finance_fee.batch if line.finance_fee_id else None
            students_grouped[key] = {
                'student': f"{student.first_name} {student.last_name} ({student.admission_no})",
                'batch': batch.name if batch else None,
                'lines': [],
            }

        # Show each particular as its own row with its own amount (e.g.
        # "Registration Fee" / "Tuition Fee" priced separately), rather than
        # collapsing them into one combined description + total. Falls back
        # to the line's own snapshot when the charge has no particulars to
        # break out (e.g. an ad-hoc charge against a category with none).
        particulars = get_finance_fee_particulars(line.finance_fee) if line.finance_fee_id else []
        if particulars:
            for p in particulars:
                students_grouped[key]['lines'].append({
                    'description': p['name'],
                    'amount_display': fmt(p['amount']),
                })
        else:
            students_grouped[key]['lines'].append({
                'description': line.description,
                'amount_display': fmt(line.amount),
            })

    return {
        'school': invoice.tenant,
        'invoice': invoice,
        'students_grouped': students_grouped,
        'subtotal_display': fmt(invoice.subtotal),
        'amount_paid_display': fmt(invoice.amount_paid),
        'balance_due_display': fmt(invoice.balance_due),
    }
