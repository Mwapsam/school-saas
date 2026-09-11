# Backfill BatchFeeCategory.is_derived/amount for categories that already
# have active FeeParticular rows, so the batch-level amount matches the sum
# of its particulars going forward (Fedena-style fee-group parity).
#
# Idempotent: recomputes the same sum on rerun. Categories with zero active
# particulars are left untouched (amount stays a manually-entered legacy
# figure, is_derived stays False).
from decimal import Decimal

from django.db import migrations
from django.db.models import Sum


def forwards(apps, schema_editor):
    FeeParticular = apps.get_model("core", "FeeParticular")
    BatchFeeCategory = apps.get_model("core", "BatchFeeCategory")

    totals_by_category = {
        row["fee_category_id"]: row["total"] or Decimal("0")
        for row in FeeParticular.objects.filter(is_active=True)
        .values("fee_category_id")
        .annotate(total=Sum("amount"))
    }

    updated = 0
    for batch_fee in BatchFeeCategory.objects.filter(
        fee_category_id__in=totals_by_category.keys()
    ):
        total = totals_by_category[batch_fee.fee_category_id]
        if batch_fee.amount != total or not batch_fee.is_derived:
            batch_fee.amount = total
            batch_fee.is_derived = True
            batch_fee.save(update_fields=["amount", "is_derived"])
            updated += 1

    if updated:
        print(f"  Marked {updated} BatchFeeCategory row(s) as derived from particulars")


def backwards(apps, schema_editor):
    # No-op: is_derived/amount are recomputable state, not data to unwind.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0082_fee_particular_due_date_and_derived_batch"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
