from django.db import migrations


def _dedup_subjects(apps, schema_editor):
    """Soft-delete duplicate subjects so the unique indexes can be created.

    Duplicates were introduced by activity-subject get_or_create calls that ran
    concurrently or repeatedly, and by code truncation collisions (e.g. two
    different skill-set names both truncating to the same 10-char code).

    Strategy: within each (tenant, batch) group, keep the row with the lowest pk
    for each case-insensitive name/code and mark the rest is_deleted=True.
    We run name dedup first, then code dedup, so a row soft-deleted by name is
    already excluded when we check for code duplicates.
    """
    Subject = apps.get_model('core', 'Subject')

    # --- deduplicate by name (case-insensitive) ---
    seen_names = {}  # (tenant_id, batch_id, lower_name) -> first pk
    for subj in Subject.objects.filter(is_deleted=False).order_by('id'):
        key = (subj.tenant_id, subj.batch_id, (subj.name or '').strip().lower())
        if key not in seen_names:
            seen_names[key] = subj.pk
        else:
            subj.is_deleted = True
            subj.save(update_fields=['is_deleted'])

    # --- deduplicate by code (case-insensitive) among remaining active rows ---
    seen_codes = {}  # (tenant_id, batch_id, lower_code) -> first pk
    for subj in Subject.objects.filter(is_deleted=False).order_by('id'):
        code = (subj.code or '').strip().lower()
        if not code:
            continue
        key = (subj.tenant_id, subj.batch_id, code)
        if key not in seen_codes:
            seen_codes[key] = subj.pk
        else:
            subj.is_deleted = True
            subj.save(update_fields=['is_deleted'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0069_extendedadmissionapplication_admitted_student'),
    ]

    operations = [
        migrations.RunPython(_dedup_subjects, migrations.RunPython.noop),
        migrations.RunSQL(
            sql=[
                """
                CREATE UNIQUE INDEX subject_batch_name_unique
                ON core_subject (tenant_id, batch_id, lower(name))
                WHERE is_deleted = false;
                """,
                """
                CREATE UNIQUE INDEX subject_batch_code_unique
                ON core_subject (tenant_id, batch_id, lower(code))
                WHERE is_deleted = false;
                """,
            ],
            reverse_sql=[
                "DROP INDEX IF EXISTS subject_batch_name_unique;",
                "DROP INDEX IF EXISTS subject_batch_code_unique;",
            ],
        ),
    ]
