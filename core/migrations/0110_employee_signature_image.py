# Generated migration for Employee.signature_image field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0109_classteacherassignment'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='signature_image',
            field=models.TextField(blank=True, default='', help_text="Base64 data-URI of the teacher's signature, printed on report cards for their assigned students. Set via the Teacher Portal signature endpoint."),
        ),
    ]
