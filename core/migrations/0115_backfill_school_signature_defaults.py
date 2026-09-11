from django.db import migrations


def backfill_default_signatures(apps, schema_editor):
    """Preserve every tenant's existing single School.signature/signature_title as
    their initial default SchoolSignature row, ahead of those fields being removed
    in the next migration. Points the new row's image at the same storage key as
    the old one (no file copy — both use the 'public' storage backend).
    """
    School = apps.get_model('core', 'School')
    SchoolSignature = apps.get_model('core', 'SchoolSignature')

    for school in School.objects.all():
        has_image = bool(school.signature and school.signature.name)
        custom_title = bool(school.signature_title and school.signature_title != 'Head of School')
        if not has_image and not custom_title:
            continue  # nothing to preserve — matches the pre-migration fallback rendering exactly

        sig = SchoolSignature(
            tenant=school,
            name='Head of School',  # placeholder — school renames to the actual signatory later
            title=school.signature_title or 'Head of School',
            is_default=True,
        )
        if has_image:
            sig.image.name = school.signature.name
        sig.save()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0114_schoolsignature_reporttemplate_signature'),
    ]

    operations = [
        migrations.RunPython(backfill_default_signatures, noop),
    ]
