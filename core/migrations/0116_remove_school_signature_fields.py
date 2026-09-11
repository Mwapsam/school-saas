from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0115_backfill_school_signature_defaults'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reporttemplate',
            name='signature_title',
        ),
        migrations.RemoveField(
            model_name='school',
            name='signature',
        ),
        migrations.RemoveField(
            model_name='school',
            name='signature_title',
        ),
    ]
