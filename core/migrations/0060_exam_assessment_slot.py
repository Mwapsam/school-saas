from django.db import migrations, models


def auto_assign_slots_from_name(apps, schema_editor):
    """
    Best-effort auto-assignment of assessment_slot for existing Exam records
    based on their exam_name field (e.g. 'ATTAINMENT' → slot ATTAINMENT).
    """
    Exam = apps.get_model('core', 'Exam')
    updates = []
    for exam in Exam.objects.all():
        name_upper = (exam.exam_name or '').upper()
        if 'ATTAINMENT' in name_upper:
            exam.assessment_slot = 'ATTAINMENT'
            updates.append(exam)
        elif 'EFFORT' in name_upper:
            exam.assessment_slot = 'EFFORT'
            updates.append(exam)
        elif 'CLASSWORK' in name_upper:
            exam.assessment_slot = 'CLASSWORK'
            updates.append(exam)
    if updates:
        Exam.objects.bulk_update(updates, ['assessment_slot'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0059_backfill_template_layout'),
    ]

    operations = [
        migrations.AddField(
            model_name='exam',
            name='assessment_slot',
            field=models.CharField(
                choices=[
                    ('EXAM', 'Examination / Test'),
                    ('ATTAINMENT', 'Attainment (Term grade)'),
                    ('EFFORT', 'Effort (Term grade)'),
                    ('CLASSWORK', 'Classwork'),
                    ('TEST', 'Test'),
                ],
                default='EXAM',
                help_text='Report column this exam feeds into (ATTAINMENT/EFFORT for grades 3-7, CLASSWORK for grades 1-2)',
                max_length=20,
            ),
        ),
        migrations.RunPython(auto_assign_slots_from_name, migrations.RunPython.noop),
    ]
