from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_add_school_logo_secondary'),
    ]

    operations = [
        migrations.AddField(
            model_name='reporttemplate',
            name='primary_color',
            field=models.CharField(
                max_length=7,
                default='#5a9e2f',
                help_text='Hex color used for report card branding (headers, accents)',
            ),
        ),
        migrations.AddField(
            model_name='reporttemplate',
            name='section_order',
            field=models.JSONField(
                default=list,
                help_text='Ordered list of section-group keys controlling PDF rendering order',
            ),
        ),
    ]
