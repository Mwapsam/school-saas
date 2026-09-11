"""Shared "what does this charge consist of" primitive.

A FinanceFee's line items come from one of two places depending on how it was
priced: an itemized FinanceFeeItem snapshot (taken when the charge was
created), or - when no such snapshot exists (lump-sum collections) - the
FeeCategory's current active FeeParticular definitions. Both the staff
receipt (FeeReportingService.student_collection_receipt) and the guardian
invoice (InvoiceService.upsert_guardian_invoice) need this same list, so it
lives here once rather than being reimplemented per caller.
"""
from datetime import date as date_cls

from core.models import FeeParticular


def applicable_particulars_for_student(fee_category, student, on_date=None) -> list:
    """Active FeeParticular rows for this category that actually apply to
    this specific student - respecting applicability_rule.matches(student)
    and effective_date/expiry_date. Two students in the same category can
    have different applicable sets (and therefore owe different amounts) -
    e.g. a "Registration Fee" scoped to one individual student shouldn't be
    charged to the rest of their batch."""
    on_date = on_date or date_cls.today()
    particulars = FeeParticular.objects.filter(
        tenant=fee_category.tenant, fee_category=fee_category, is_active=True,
    ).select_related('applicability_rule')
    return [
        p for p in particulars
        if not (p.effective_date and on_date < p.effective_date)
        and not (p.expiry_date and on_date > p.expiry_date)
        and (p.applicability_rule is None or p.applicability_rule.matches(student))
    ]


def get_finance_fee_particulars(finance_fee) -> list[dict]:
    """[{'name', 'amount'}, ...] for a charge's line items, largest first -
    there's no priority/display-order field on FeeParticular to sort by, so
    amount descending is the closest thing to a stable, meaningful order."""
    items = list(finance_fee.items.all())
    if items:
        return [
            {'name': i.particular_name, 'amount': i.amount}
            for i in sorted(items, key=lambda i: i.amount, reverse=True)
        ]
    # No snapshot (a legacy or un-reconciled charge) - fall back to the
    # category's currently-applicable particulars for this specific student,
    # not every active particular in the category (some may be scoped away
    # from this student entirely).
    applicable = applicable_particulars_for_student(finance_fee.fee_category, finance_fee.student)
    return [
        {'name': p.name, 'amount': p.amount}
        for p in sorted(applicable, key=lambda p: p.amount, reverse=True)
    ]


def describe_finance_fee(finance_fee) -> str:
    """Comma-joined particular names for a charge's line-item description -
    falls back to the fee category's name when no particulars are found."""
    names = [p['name'] for p in get_finance_fee_particulars(finance_fee)]
    return ", ".join(names) if names else finance_fee.fee_category.name
