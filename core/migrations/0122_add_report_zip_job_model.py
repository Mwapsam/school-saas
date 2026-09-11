# Generated migration for adding ReportZipJob model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0121_add_news_document'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportZipJob',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('file_path', models.CharField(blank=True, help_text='Storage path to the ZIP file once completed', max_length=500)),
                ('total_reports', models.IntegerField(default=0, help_text='Total reports to include in the ZIP')),
                ('processed_reports', models.IntegerField(default=0, help_text='Reports added to ZIP so far')),
                ('error_message', models.TextField(blank=True, help_text='Error details if the job failed')),
                ('expires_at', models.DateTimeField(help_text='When this job and its ZIP file should be cleaned up')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.school')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zip_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='reportzipjob',
            index=models.Index(fields=['tenant', 'status'], name='core_reportz_tenant__6d8c0e_idx'),
        ),
        migrations.AddIndex(
            model_name='reportzipjob',
            index=models.Index(fields=['tenant', 'requested_by'], name='core_reportz_tenant__3f2a1b_idx'),
        ),
        migrations.AddIndex(
            model_name='reportzipjob',
            index=models.Index(fields=['tenant', 'expires_at'], name='core_reportz_tenant__e4c9d2_idx'),
        ),
    ]
