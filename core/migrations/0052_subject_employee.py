from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_finance_payment_method'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='employee',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='subjects_taught',
                to='core.employee',
                help_text='Teacher assigned to this subject within its batch',
            ),
        ),
    ]
