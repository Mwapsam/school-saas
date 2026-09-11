# Generated migration for Phase 1: Add Term.academic_year

from django.db import migrations, models
import django.db.models.deletion


def backfill_academic_year(apps, schema_editor):
    """Backfill academic_year for all existing Term rows via exam_group.batch.academic_year"""
    Term = apps.get_model("core", "Term")
    updated = 0
    anomalies = []

    for term in Term.objects.select_related("exam_group__batch__academic_year").all():
        try:
            if term.exam_group and term.exam_group.batch and term.exam_group.batch.academic_year:
                term.academic_year = term.exam_group.batch.academic_year
                term.save(update_fields=["academic_year"])
                updated += 1
            else:
                anomalies.append(
                    f"Term {term.id}: exam_group={term.exam_group_id}, "
                    f"batch={term.exam_group.batch_id if term.exam_group else None}, "
                    f"academic_year={term.exam_group.batch.academic_year_id if (term.exam_group and term.exam_group.batch) else None}"
                )
        except Exception as e:
            anomalies.append(f"Term {term.id}: {str(e)}")

    if anomalies:
        print(f"\n[WARNING] Backfill completed with {len(anomalies)} anomalies:")
        for anomaly in anomalies:
            print(f"  - {anomaly}")
    print(f"\n[INFO] Backfilled academic_year for {updated} Term rows")


def reverse_backfill(apps, schema_editor):
    """Reverse: clear academic_year values (but keep the column for rollback safety)"""
    Term = apps.get_model("core", "Term")
    Term.objects.all().update(academic_year=None)
    print("[INFO] Cleared academic_year values for all Term rows")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0134_backfill_sms_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="term",
            name="academic_year",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="terms_by_year",
                to="core.academicyear",
            ),
        ),
        migrations.AddIndex(
            model_name="term",
            index=models.Index(fields=["tenant", "academic_year"], name="core_term_tenant_ac_idx"),
        ),
        migrations.RunPython(backfill_academic_year, reverse_backfill),
    ]
