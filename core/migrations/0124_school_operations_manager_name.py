# Generated migration for adding operations_manager_name field to School model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0123_rename_core_reportz_tenant__6d8c0e_idx_core_report_tenant__f16353_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='school',
            name='operations_manager_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Operations Manager name for payment agreements',
                max_length=255
            ),
        ),
    ]
