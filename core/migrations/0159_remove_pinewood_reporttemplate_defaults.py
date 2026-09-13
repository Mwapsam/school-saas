# Generated manually — Phase 1.1: Remove hardcoded Pinewood defaults from ReportTemplate

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0158_alter_applicantenquiry_enquired_date_and_more'),
    ]

    operations = [
        # Remove hardcoded Pinewood school identity defaults
        migrations.AlterField(
            model_name='reporttemplate',
            name='school_name',
            field=models.CharField(
                blank=True, null=True, max_length=255,
                help_text="Sourced from tenant at creation; left blank to use tenant values at display time"
            ),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='school_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='school_contact',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='school_email',
            field=models.EmailField(max_length=254, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='reporttemplate',
            name='school_website',
            field=models.URLField(blank=True, null=True),
        ),
        # Remove hardcoded Pinewood green color
        migrations.AlterField(
            model_name='reporttemplate',
            name='primary_color',
            field=models.CharField(
                blank=True, null=True, max_length=7,
                help_text='Hex color for report card headers and accents; sourced from tenant if not set'
            ),
        ),
    ]
