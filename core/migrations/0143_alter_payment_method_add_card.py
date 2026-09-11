from django.db import migrations, models


CHOICES = [
    ('cash', 'Cash'),
    ('card', 'Card'),
    ('bank_transfer', 'Bank Transfer'),
    ('mobile_money', 'Mobile Money'),
    ('cheque', 'Cheque'),
    ('online', 'Online Payment'),
    ('other', 'Other'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0142_rename_core_feecp_tenant_idx_core_feecol_tenant__83a486_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='financetransaction',
            name='payment_method',
            field=models.CharField(
                blank=True, choices=CHOICES, default='cash', max_length=20,
                help_text='Method used for this transaction',
            ),
        ),
        migrations.AlterField(
            model_name='feetransaction',
            name='payment_method',
            field=models.CharField(
                blank=True, choices=CHOICES, default='cash', max_length=20,
                help_text='Payment method used',
            ),
        ),
    ]
