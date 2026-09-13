# Generated migration for DemoRequest model

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0163_school_branding_config'),
    ]

    operations = [
        migrations.CreateModel(
            name='DemoRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('full_name', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('school_name', models.CharField(blank=True, help_text='Name of the prospective school/organization', max_length=255)),
                ('message', models.TextField(blank=True, help_text='Additional message or inquiry')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('contacted', 'Contacted'),
                        ('demo_scheduled', 'Demo Scheduled'),
                        ('converted', 'Converted'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                    max_length=20
                )),
                ('notes', models.TextField(blank=True, help_text='Internal notes from admin')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='demorequest',
            index=models.Index(fields=['email'], name='core_demorea_email_idx'),
        ),
        migrations.AddIndex(
            model_name='demorequest',
            index=models.Index(fields=['status'], name='core_demorea_status_idx'),
        ),
        migrations.AddIndex(
            model_name='demorequest',
            index=models.Index(fields=['-created_at'], name='core_demorea_created_at_idx'),
        ),
    ]
