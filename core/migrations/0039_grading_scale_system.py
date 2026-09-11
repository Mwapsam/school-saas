# Generated migration for Dynamic Grading Scale System

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_activity_assessment_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='GradingScale',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255, help_text='e.g., Letter Grades, Descriptive Grades, Numeric Percentage')),
                ('code', models.CharField(max_length=50, help_text='Unique code for programmatic access')),
                ('scale_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('LETTER', 'Letter Grades (A, B, C, D, E, F)'),
                        ('DESCRIPTIVE', 'Descriptive (Very Good, Good, Satisfactory, Weak)'),
                        ('NUMERIC', 'Numeric Marks'),
                        ('LEVEL', 'Skill Levels (Not Yet, Beginning, Satisfactory, Good)'),
                        ('BINARY', 'Pass/Fail or Y/N'),
                        ('CUSTOM', 'Custom Grade Set'),
                    ],
                    help_text='Type of grading scale'
                )),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False, help_text='Default scale for new subjects')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grading_scales', to='core.school')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['tenant', 'is_active'], name='core_gradin_tenant__active_idx'),
                    models.Index(fields=['code'], name='core_gradin_code_idx'),
                ],
                'unique_together': {('tenant', 'code')},
            },
        ),
        migrations.CreateModel(
            name='GradeValue',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('grading_scale', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grade_values', to='core.gradingscale')),
                ('name', models.CharField(max_length=100, help_text='Display name: A, Very Good, 90-100, etc.')),
                ('code', models.CharField(max_length=50, help_text='Internal code for programmatic access')),
                ('min_percentage', models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Minimum percentage for this grade (0-100)')),
                ('max_percentage', models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Maximum percentage for this grade (0-100)')),
                ('gpa_value', models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text='GPA equivalent (e.g., 4.0 for A)')),
                ('display_order', models.IntegerField(default=0, help_text='Order in dropdowns and reports')),
                ('is_passing', models.BooleanField(default=True, help_text='Whether this grade is considered passing')),
                ('color_code', models.CharField(max_length=7, blank=True, null=True, help_text='Hex color for UI display (#FF0000)')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grade_values', to='core.school')),
            ],
            options={
                'ordering': ['display_order', 'name'],
                'indexes': [
                    models.Index(fields=['tenant', 'grading_scale'], name='core_gradev_tenant__scale_idx'),
                    models.Index(fields=['grading_scale', 'display_order'], name='core_gradev_scale__order_idx'),
                ],
            },
        ),
        migrations.AddField(
            model_name='subject',
            name='grading_scale',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='subjects',
                to='core.gradingscale',
                help_text='Grading scale for this subject (overrides batch default)'
            ),
        ),
        migrations.AddField(
            model_name='subjectskillset',
            name='grading_scale',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='subject_skill_sets_custom',
                to='core.gradingscale',
                help_text='Custom grading scale for this skill set (overrides subject default)'
            ),
        ),
        migrations.AddField(
            model_name='batch',
            name='default_grading_scale',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='batches',
                to='core.gradingscale',
                help_text='Default grading scale for all subjects in this batch'
            ),
        ),
    ]