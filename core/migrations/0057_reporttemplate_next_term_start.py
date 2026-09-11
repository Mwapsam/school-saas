from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0056_school_report_branding'),
    ]

    operations = [
        migrations.AddField(
            model_name='reporttemplate',
            name='next_term_start',
            field=models.DateField(
                null=True, blank=True,
                help_text='Overrides the auto-detected "Next term commences" date on the report',
            ),
        ),
    ]
