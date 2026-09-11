from django.db import migrations, models


def backfill_report_layout(apps, schema_editor):
    """Tag existing grading scales with a sensible report format.

    Skill-level scales drive the Skills checklist; everything else defaults to
    the Full Academic format (institutions can adjust to Simple Academic per
    scheme via admin)."""
    GradingScale = apps.get_model('core', 'GradingScale')
    GradingScale.objects.filter(scale_type='LEVEL').update(report_layout='SKILLS')
    GradingScale.objects.exclude(scale_type='LEVEL').filter(
        report_layout=''
    ).update(report_layout='FULL_ACADEMIC')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0054_alter_batch_employee'),
    ]

    operations = [
        migrations.AddField(
            model_name='reporttemplate',
            name='include_skills',
            field=models.BooleanField(
                default=True,
                help_text='Show the skills checklist (Skills layout only)',
            ),
        ),
        migrations.AddField(
            model_name='gradingscale',
            name='report_layout',
            field=models.CharField(
                blank=True,
                max_length=20,
                choices=[
                    ('SKILLS', 'Skills Checklist (Beginners / Reception)'),
                    ('SIMPLE_ACADEMIC', 'Simple Academic (Grade 1–2)'),
                    ('FULL_ACADEMIC', 'Full Academic (Grade 3–7)'),
                ],
                help_text='Report card format produced by this scheme (drives the report template layout)',
            ),
        ),
        migrations.RunPython(backfill_report_layout, noop),
    ]
