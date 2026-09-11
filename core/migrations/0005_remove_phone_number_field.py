# Generated manually to fix phone_number field issue
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_update_extended_admission_multistep'),
    ]

    operations = [
        # Remove the old phone_number field that was causing NOT NULL constraint issues
        migrations.RemoveField(
            model_name='extendedadmissionapplication',
            name='phone_number',
        ),
    ]