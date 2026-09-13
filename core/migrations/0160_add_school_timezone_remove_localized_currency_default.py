# Generated manually — Phase 1.1: Add timezone to School, remove hardcoded currency fallback

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0159_remove_pinewood_reporttemplate_defaults'),
    ]

    operations = [
        # Add timezone field to School model for per-tenant timezone configuration
        migrations.AddField(
            model_name='school',
            name='timezone',
            field=models.CharField(
                default='UTC', max_length=63,
                help_text="IANA timezone identifier (e.g., 'Africa/Nairobi', 'UTC', 'America/New_York'). "
                          "Used to display times in the tenant's local timezone."
            ),
        ),
    ]
