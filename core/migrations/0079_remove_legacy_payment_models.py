from django.db import migrations


class Migration(migrations.Migration):
    """Drop the legacy PaymentMethod/FeeInvoice/PaymentTransaction models.

    Confirmed unused anywhere outside their own model definitions/migrations
    and an admin registration - superseded by FinanceFee/FeeTransaction and
    the new FamilyInvoice ledger.
    """

    dependencies = [
        ('core', '0078_guardian_centric_qb_invoicing'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='feeinvoice',
            name='academic_year',
        ),
        migrations.RemoveField(
            model_name='feeinvoice',
            name='fee_category',
        ),
        migrations.RemoveField(
            model_name='feeinvoice',
            name='student',
        ),
        migrations.RemoveField(
            model_name='feeinvoice',
            name='tenant',
        ),
        migrations.RemoveField(
            model_name='paymenttransaction',
            name='invoice',
        ),
        migrations.RemoveField(
            model_name='paymenttransaction',
            name='payment_method',
        ),
        migrations.RemoveField(
            model_name='paymenttransaction',
            name='processed_by',
        ),
        migrations.RemoveField(
            model_name='paymenttransaction',
            name='student',
        ),
        migrations.RemoveField(
            model_name='paymenttransaction',
            name='tenant',
        ),
        migrations.RemoveField(
            model_name='paymentmethod',
            name='tenant',
        ),
        migrations.DeleteModel(
            name='FeeInvoice',
        ),
        migrations.DeleteModel(
            name='PaymentTransaction',
        ),
        migrations.DeleteModel(
            name='PaymentMethod',
        ),
    ]
