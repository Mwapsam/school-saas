# Generated migration to remove amount and is_derived from BatchFeeCategory

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0095_feecollection_frequency_feecollection_late_fee_rule_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='batchfeecategory',
            name='amount',
        ),
        migrations.RemoveField(
            model_name='batchfeecategory',
            name='is_derived',
        ),
    ]
