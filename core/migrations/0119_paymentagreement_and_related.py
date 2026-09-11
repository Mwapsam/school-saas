# Generated migration for Payment Agreement models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0118_add_book_classification'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentAgreement',
            fields=[
                ('id', models.UUIDField(default=models.BigAutoField, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('debtor_name', models.CharField(max_length=255)),
                ('nrc_number', models.CharField(blank=True, max_length=50, null=True)),
                ('debtor_address', models.TextField(blank=True, null=True)),
                ('unpaid_fees_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('other_amount', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('other_description', models.TextField(blank=True, null=True)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('interest_rate', models.DecimalField(decimal_places=2, default=5, max_digits=5)),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'),
                        ('active', 'Active'),
                        ('completed', 'Completed'),
                        ('defaulted', 'Defaulted'),
                        ('cancelled', 'Cancelled')
                    ],
                    default='draft',
                    max_length=20
                )),
                ('debtor_signed_date', models.DateField(blank=True, null=True)),
                ('witness_name', models.CharField(blank=True, max_length=255, null=True)),
                ('witness_signed_date', models.DateField(blank=True, null=True)),
                ('director_name', models.CharField(blank=True, default='', max_length=255)),
                ('director_signed_date', models.DateField(blank=True, null=True)),
                ('director_witness_name', models.CharField(blank=True, default='', max_length=255)),
                ('director_witness_signed_date', models.DateField(blank=True, null=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_agreements_created', to=settings.AUTH_USER_MODEL)),
                ('guardian', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_agreements', to='core.guardian')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_agreements', to='core.student')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.school')),
            ],
            options={
                'db_table': 'core_paymentagreement',
            },
        ),
        migrations.CreateModel(
            name='PaymentAgreementPaymentRecord',
            fields=[
                ('id', models.UUIDField(default=models.BigAutoField, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('payment_date', models.DateField()),
                ('amount_paid', models.DecimalField(decimal_places=2, max_digits=15)),
                ('balance_after', models.DecimalField(decimal_places=2, max_digits=15)),
                ('agreement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_records', to='core.paymentagreement')),
                ('fee_transaction', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_agreement_record', to='core.feetransaction')),
                ('recorded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_agreement_records', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.school')),
            ],
            options={
                'db_table': 'core_paymentagreementpaymentrecord',
                'ordering': ['-payment_date'],
            },
        ),
        migrations.CreateModel(
            name='PaymentAgreementInstallment',
            fields=[
                ('id', models.UUIDField(default=models.BigAutoField, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sequence', models.PositiveIntegerField()),
                ('due_date', models.DateField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('agreement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='installments', to='core.paymentagreement')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.school')),
            ],
            options={
                'db_table': 'core_paymentagreementinstallment',
                'ordering': ['sequence'],
            },
        ),
    ]
