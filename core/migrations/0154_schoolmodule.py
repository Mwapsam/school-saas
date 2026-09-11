# Generated migration for SchoolModule model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0153_policydocument_policyacknowledgement_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SchoolModule',
            fields=[
                ('id', models.UUIDField(default=None, editable=False, primary_key=True, serialize=False)),
                ('module', models.CharField(help_text="Module key (e.g. 'finance', 'hr', 'hostel') — must match core.modules.MODULES", max_length=50)),
                ('enabled', models.BooleanField(default=True, help_text='Whether this module is currently active for the school')),
                ('configuration', models.JSONField(blank=True, default=dict, help_text='Module-specific configuration (e.g. {transport: {fleet_management: true}}). Allows future extensibility without schema rewrites.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.school')),
                ('school', models.ForeignKey(help_text='School that owns this module configuration', on_delete=django.db.models.deletion.CASCADE, related_name='modules', to='core.school')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddIndex(
            model_name='schoolmodule',
            index=models.Index(fields=['school', 'enabled'], name='core_schoolm_school_enabled_idx'),
        ),
        migrations.AddIndex(
            model_name='schoolmodule',
            index=models.Index(fields=['module'], name='core_schoolm_module_idx'),
        ),
        migrations.AddConstraint(
            model_name='schoolmodule',
            constraint=models.UniqueConstraint(fields=('school', 'module'), name='unique_school_module'),
        ),
    ]
