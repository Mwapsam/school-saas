# Generated migration for adding classroom field and unique_together constraint to Timetable

from django.db import migrations, models


def remove_duplicates(apps, schema_editor):
    """Remove duplicate Timetable entries, keeping the most recently updated one per group."""
    from django.db.models import Count, Max

    Timetable = apps.get_model('core', 'Timetable')

    # Find all duplicate groups
    try:
        duplicates = (
            Timetable.objects
            .values('tenant_id', 'batch_id', 'weekday_id', 'class_timing_id')
            .annotate(count=Count('id'))
            .filter(count__gt=1)
        )

        for dup in duplicates:
            group = Timetable.objects.filter(
                tenant_id=dup['tenant_id'],
                batch_id=dup['batch_id'],
                weekday_id=dup['weekday_id'],
                class_timing_id=dup['class_timing_id']
            )

            # Keep the most recently updated entry
            most_recent = group.latest('updated_at')

            # Delete all others
            group.exclude(id=most_recent.id).delete()
    except Exception:
        # Silently pass if there are any issues
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0088_add_batch_exam_type_configuration'),
    ]

    operations = [
        migrations.AddField(
            model_name='timetable',
            name='classroom',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.RunPython(remove_duplicates, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='timetable',
            unique_together={('batch', 'weekday', 'class_timing')},
        ),
    ]
