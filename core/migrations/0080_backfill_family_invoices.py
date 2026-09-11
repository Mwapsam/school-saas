# Backfill FamilyInvoice/FamilyInvoiceLine from existing local data, and mark
# legacy student-keyed QuickBooksCustomerSync/QuickBooksFeeInvoiceSync rows as
# "outdated" now that the customer/invoice unit is the guardian, not the
# student.
#
# A guardian with N children previously had N separate QB customers/invoices;
# there is no reliable way to pick one as canonical, so the legacy rows are
# left in place (for audit) but excluded from active use. The very first
# charge/payment for a family after deploy lazily creates a fresh, correctly
# consolidated QB customer + invoice via QuickBooksFeeSync.
#
# The local FamilyInvoice/FamilyInvoiceLine backfill is pure local data and
# safe to run repeatedly: FamilyInvoiceLine.finance_fee is unique, so a
# second run only creates rows for FinanceFee charges that don't have one yet.
from collections import defaultdict
from decimal import Decimal

from django.db import migrations


def _invoice_number(tenant_id, guardian_id, academic_year_id, seq):
    return f"INV-{str(tenant_id)[:8]}-{str(academic_year_id)[:8]}-{seq:06d}"


def forwards(apps, schema_editor):
    FinanceFee = apps.get_model("core", "FinanceFee")
    FeeTransaction = apps.get_model("core", "FeeTransaction")
    Student = apps.get_model("core", "Student")
    FamilyInvoice = apps.get_model("core", "FamilyInvoice")
    FamilyInvoiceLine = apps.get_model("core", "FamilyInvoiceLine")
    QuickBooksCustomerSync = apps.get_model("core", "QuickBooksCustomerSync")
    QuickBooksFeeInvoiceSync = apps.get_model("core", "QuickBooksFeeInvoiceSync")

    QuickBooksCustomerSync.objects.filter(guardian__isnull=True).update(sync_status="outdated")
    QuickBooksFeeInvoiceSync.objects.filter(guardian__isnull=True).update(sync_status="outdated")

    immediate_contact_by_student = dict(
        Student.objects.exclude(immediate_contact__isnull=True).values_list(
            "id", "immediate_contact_id"
        )
    )

    already_lined = set(
        FamilyInvoiceLine.objects.values_list("finance_fee_id", flat=True)
    )

    fees = list(
        FinanceFee.objects.exclude(academic_year__isnull=True).values(
            "id", "tenant_id", "student_id", "academic_year_id", "balance",
            "fee_category__name",
        )
    )

    payment_totals = defaultdict(Decimal)
    for t in FeeTransaction.objects.filter(
        transaction_type__in=["payment", "refund"]
    ).values("student_id", "fee_category_id", "academic_year_id", "transaction_type", "amount"):
        key = (t["student_id"], t["fee_category_id"], t["academic_year_id"])
        amt = t["amount"] or Decimal("0")
        payment_totals[key] += amt if t["transaction_type"] == "payment" else -amt

    invoices_by_key = {}
    seq_by_scope = defaultdict(int)
    created_invoices = 0
    created_lines = 0

    for fee in fees:
        if fee["id"] in already_lined:
            continue
        guardian_id = immediate_contact_by_student.get(fee["student_id"])
        if not guardian_id:
            continue

        inv_key = (fee["tenant_id"], guardian_id, fee["academic_year_id"])
        invoice = invoices_by_key.get(inv_key)
        if invoice is None:
            invoice = FamilyInvoice.objects.filter(
                tenant_id=fee["tenant_id"], guardian_id=guardian_id,
                academic_year_id=fee["academic_year_id"],
            ).first()
        if invoice is None:
            seq_by_scope[(fee["tenant_id"], fee["academic_year_id"])] += 1
            seq = seq_by_scope[(fee["tenant_id"], fee["academic_year_id"])]
            invoice = FamilyInvoice.objects.create(
                tenant_id=fee["tenant_id"], guardian_id=guardian_id,
                academic_year_id=fee["academic_year_id"],
                invoice_number=_invoice_number(
                    fee["tenant_id"], guardian_id, fee["academic_year_id"], seq
                ),
            )
            created_invoices += 1
        invoices_by_key[inv_key] = invoice

        FamilyInvoiceLine.objects.create(
            tenant_id=fee["tenant_id"], invoice=invoice, student_id=fee["student_id"],
            finance_fee_id=fee["id"], academic_year_id=fee["academic_year_id"],
            description=fee["fee_category__name"] or "Fee charge",
            amount=fee["balance"] or Decimal("0"),
        )
        created_lines += 1

    # Recompute totals for every touched invoice from its lines + payments.
    for invoice in invoices_by_key.values():
        lines = list(invoice.lines.all().values("student_id", "amount", "academic_year_id"))
        subtotal = sum((l["amount"] for l in lines), Decimal("0"))
        paid = Decimal("0")
        for l in lines:
            fee_categories = FinanceFee.objects.filter(
                family_invoice_line__invoice=invoice,
                student_id=l["student_id"],
                academic_year_id=l["academic_year_id"],
            ).values_list("fee_category_id", flat=True)
            for fee_category_id in fee_categories:
                paid += payment_totals.get(
                    (l["student_id"], fee_category_id, l["academic_year_id"]), Decimal("0")
                )
        balance_due = subtotal - paid
        FamilyInvoice.objects.filter(pk=invoice.pk).update(
            subtotal=subtotal, total_amount=subtotal, amount_paid=paid,
            balance_due=balance_due,
            status="paid" if balance_due <= 0 else "open",
        )

    if created_invoices or created_lines:
        print(f"  Backfilled {created_invoices} FamilyInvoice(s), {created_lines} FamilyInvoiceLine(s)")


def backwards(apps, schema_editor):
    # No-op: FamilyInvoice/FamilyInvoiceLine rows are local data, not derived
    # state that needs unwinding; leaving them is harmless on rollback.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0079_remove_legacy_payment_models"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
