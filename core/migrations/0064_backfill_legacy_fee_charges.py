# Backfill charge ledger rows for legacy FinanceFee charges.
#
# Charges created before the ledger overhaul have no FeeTransaction("adjustment")
# row, so per-student statements showed total_charged = 0 even though the closing
# balance was correct. This migration reconstructs the missing charge total per
# (tenant, student, fee_category, academic_year) group so statements reconcile:
#
#   target_charged = Σ FinanceFee.balance + Σ payments + Σ discounts − Σ fines
#   missing        = target_charged − Σ existing charge (adjustment) rows
#
# When missing > 0 a single backfilled "adjustment" charge row is written, dated
# at the group's earliest charge date. Idempotent: a second run computes
# missing == 0 because the backfilled row is now part of the existing total.
from collections import defaultdict
from decimal import Decimal

from django.db import migrations


def _group_key(row):
    return (row["tenant_id"], row["student_id"], row["fee_category_id"], row["academic_year_id"])


def forwards(apps, schema_editor):
    FinanceFee = apps.get_model("core", "FinanceFee")
    FeeTransaction = apps.get_model("core", "FeeTransaction")

    # Sum existing ledger amounts per group, split by what they represent.
    charges = defaultdict(Decimal)   # adjustment rows = charges/opening/particulars
    payments = defaultdict(Decimal)
    discounts = defaultdict(Decimal)
    fines = defaultdict(Decimal)
    for t in FeeTransaction.objects.all().values(
        "tenant_id", "student_id", "fee_category_id", "academic_year_id",
        "transaction_type", "amount",
    ):
        key = _group_key(t)
        amt = t["amount"] or Decimal("0")
        ttype = t["transaction_type"]
        if ttype == "adjustment":
            charges[key] += amt
        elif ttype == "payment":
            payments[key] += amt
        elif ttype == "discount":
            discounts[key] += amt
        elif ttype == "fine":
            fines[key] += amt

    # Balance + earliest date per FinanceFee group.
    balances = defaultdict(Decimal)
    earliest_date = {}
    for f in FinanceFee.objects.all().values(
        "tenant_id", "student_id", "fee_category_id", "academic_year_id",
        "balance", "transaction_date", "created_at",
    ):
        key = _group_key(f)
        balances[key] += f["balance"] or Decimal("0")
        d = f["transaction_date"] or (f["created_at"].date() if f["created_at"] else None)
        if d is not None and (key not in earliest_date or d < earliest_date[key]):
            earliest_date[key] = d

    created = 0
    for key, balance_total in balances.items():
        tenant_id, student_id, fee_category_id, academic_year_id = key
        target = balance_total + payments[key] + discounts[key] - fines[key]
        missing = target - charges[key]
        if missing <= 0:
            continue

        row = FeeTransaction.objects.create(
            tenant_id=tenant_id, student_id=student_id, fee_category_id=fee_category_id,
            academic_year_id=academic_year_id, transaction_type="adjustment",
            amount=missing, description="Opening charge (backfilled from balance history)",
        )
        # transaction_date is auto_now_add; reset it to the group's earliest date
        # via update() so the statement orders it correctly.
        d = earliest_date.get(key)
        if d is not None:
            FeeTransaction.objects.filter(pk=row.pk).update(transaction_date=d)
        created += 1

    if created:
        print(f"  Backfilled {created} legacy charge ledger row(s)")


def backwards(apps, schema_editor):
    # Remove only the rows this migration created (identifiable by description).
    FeeTransaction = apps.get_model("core", "FeeTransaction")
    FeeTransaction.objects.filter(
        transaction_type="adjustment",
        description="Opening charge (backfilled from balance history)",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0063_add_qb_sync_backrefs"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
