# Generated migration for enhanced SubjectSkillSet model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_add_term_to_exam'),
    ]

    operations = [
        migrations.AddField(
            model_name='subjectskillset',
            name='assessment_mode',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('DESCRIPTIVE', 'Descriptive Levels Only'),
                    ('NUMERIC', 'Convert to Numeric Marks'),
                    ('HYBRID', 'Both Levels and Marks'),
                    ('ACTIVITY', 'Activity-Based Assessment'),
                ],
                default='DESCRIPTIVE',
                help_text='How skills are assessed and reported'
            ),
        ),
        migrations.AddField(
            model_name='subjectskillset',
            name='weight_in_final_grade',
            field=models.DecimalField(
                max_digits=5,
                decimal_places=2,
                null=True,
                blank=True,
                help_text='Percentage weight if contributing to final grade (0-100)'
            ),
        ),
        migrations.AddField(
            model_name='subjectskillset',
            name='grading_profile',
            field=models.ForeignKey(
                'GradingLevel',
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name='subject_skill_sets',
                help_text='Grading profile for activity-based assessments'
            ),
        ),
        migrations.AddField(
            model_name='subjectskillset',
            name='is_active',
            field=models.BooleanField(
                default=True,
                help_text='Whether this skill set is currently used for assessments'
            ),
        ),
        migrations.AddField(
            model_name='subjectskillset',
            name='display_order',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Order in which skill sets appear in reports'
            ),
        ),
    ]