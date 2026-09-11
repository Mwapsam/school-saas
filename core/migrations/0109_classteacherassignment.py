# Generated migration for ClassTeacherAssignment model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0108_activitiessavecheckpoint'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassTeacherAssignment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('reason', models.CharField(blank=True, default='', max_length=255)),
                ('deactivated_at', models.DateTimeField(blank=True, null=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_teacher_assignments', to='core.batch')),
                ('deactivated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_teacher_assignments', to='core.employee')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_teacher_assignments', to='core.student')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_set', to='core.school')),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='class_teacher_assignments', to='core.academicyear')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddIndex(
            model_name='classteacherassignment',
            index=models.Index(fields=['tenant', 'batch', 'is_active'], name='core_classtte_tenant_batch_idx'),
        ),
        migrations.AddIndex(
            model_name='classteacherassignment',
            index=models.Index(fields=['tenant', 'student', 'is_active'], name='core_classtte_tenant_stud_idx'),
        ),
        migrations.AddIndex(
            model_name='classteacherassignment',
            index=models.Index(fields=['tenant', 'employee', 'is_active'], name='core_classtte_tenant_empl_idx'),
        ),
        migrations.AddConstraint(
            model_name='classteacherassignment',
            constraint=models.UniqueConstraint(condition=models.Q(('is_active', True)), fields=['student', 'batch', 'academic_year'], name='uniq_active_class_teacher_assignment'),
        ),
    ]
