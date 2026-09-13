# Generated manually — Phase 1.1: Remove hardcoded Pinewood defaults from configuration models

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0160_add_school_timezone_remove_localized_currency_default'),
    ]

    operations = [
        # QuickBooks: Remove hardcoded 30-day payment terms default
        migrations.AlterField(
            model_name='quickbooksconfiguration',
            name='payment_terms_days',
            field=models.IntegerField(
                null=True, blank=True,
                help_text='Default payment terms in days (tenant-configurable; no Pinewood default)'
            ),
        ),
        # Transport: Remove hardcoded "termly" billing frequency default
        migrations.AlterField(
            model_name='transportsettings',
            name='billing_frequency',
            field=models.CharField(
                max_length=20, null=True, blank=True,
                choices=[
                    ('one_time', 'One Time'),
                    ('monthly', 'Monthly'),
                    ('termly', 'Termly'),
                    ('yearly', 'Yearly'),
                ],
                help_text='How often transport fees are billed (tenant-configurable; no Pinewood default)'
            ),
        ),
        # ReportTemplate: Change section inclusion flags from all=True to all=False
        # (tenant-configurable, no Pinewood assumptions)
        migrations.AlterField(
            model_name='reporttemplate',
            name='include_exam_scores',
            field=models.BooleanField(
                default=False, help_text='Include exam scores in report'
            ),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='include_homework_assessment',
            field=models.BooleanField(
                default=False, help_text='Include homework assessment in report'
            ),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='include_project_work',
            field=models.BooleanField(
                default=False, help_text='Include project work in report'
            ),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='include_clubs',
            field=models.BooleanField(
                default=False, help_text='Include club participation in report'
            ),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='include_sports',
            field=models.BooleanField(
                default=False, help_text='Include sports participation in report'
            ),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='include_other_activities',
            field=models.BooleanField(
                default=False, help_text='Include other activities in report'
            ),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='include_attendance',
            field=models.BooleanField(
                default=False, help_text='Include attendance data in report'
            ),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='include_grading_scale',
            field=models.BooleanField(
                default=False, help_text='Include grading scale reference in report'
            ),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='include_skills',
            field=models.BooleanField(
                default=False,
                help_text='Show the skills checklist (Skills layout only)'
            ),
        ),
    ]
