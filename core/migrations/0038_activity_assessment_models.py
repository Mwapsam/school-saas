# Generated migration for Activity Assessment models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_enhance_subject_skillset_assessment'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255, help_text='e.g., CLUBS, SPORTS, PROJECT WORK, HOMEWORK')),
                ('display_name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_profiles', to='core.school')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['tenant', 'is_active'], name='core_activi_tenant__idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255, help_text='e.g., Chess, Art and Craft, Drama')),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('activity_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='core.activityprofile')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='core.school')),
            ],
            options={
                'verbose_name_plural': 'Activities',
                'indexes': [
                    models.Index(fields=['tenant', 'activity_profile'], name='core_activi_tenant__profile_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ActivityAssessment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('activity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='core.activity')),
                ('subject_skill_set', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_assessments', to='core.subjectskillset', help_text='Links to subject configured for activity assessment')),
                ('term', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='activity_assessments', to='core.term')),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_assessments', to='core.academicyear')),
                ('assessment_date', models.DateField()),
                ('is_published', models.BooleanField(default=False)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_assessments', to='core.school')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['tenant', 'subject_skill_set', 'term'], name='core_activi_tenant__sss_term_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ActivityGrade',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('activity_assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grades', to='core.activityassessment')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_grades', to='core.student')),
                ('grading_level', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_grades', to='core.gradinglevel', help_text='Grade: A/B/C/D/E/F')),
                ('remarks', models.TextField(blank=True, null=True)),
                ('is_absent', models.BooleanField(default=False)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activity_grades', to='core.school')),
            ],
            options={
                'unique_together': {('activity_assessment', 'student', 'tenant')},
                'indexes': [
                    models.Index(fields=['tenant', 'student'], name='core_activi_tenant__student_idx'),
                    models.Index(fields=['activity_assessment', 'student'], name='core_activi_assess__student_idx'),
                ],
            },
        ),
    ]