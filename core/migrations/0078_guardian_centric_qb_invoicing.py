import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0077_rename_core_skills_tenant__batch__term_idx_core_skills_tenant__55010f_idx_and_more'),
    ]

    operations = [
        # --- New local source-of-truth models ---------------------------------
        migrations.CreateModel(
            name='FamilyInvoice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('invoice_number', models.CharField(max_length=50, unique=True)),
                ('status', models.CharField(choices=[('open', 'Open'), ('paid', 'Paid'), ('void', 'Void')], default='open', max_length=20)),
                ('subtotal', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('amount_paid', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('balance_due', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('last_updated_at', models.DateTimeField(auto_now=True)),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='family_invoices', to='core.academicyear')),
                ('guardian', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='family_invoices', to='core.guardian')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_set', to='core.school')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['tenant', 'guardian', 'academic_year'], name='core_family_tenant__213dd1_idx'),
                    models.Index(fields=['tenant', 'status'], name='core_family_tenant__b5d103_idx'),
                ],
                'unique_together': {('tenant', 'guardian', 'academic_year')},
            },
        ),
        migrations.CreateModel(
            name='FamilyInvoiceLine',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('description', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.academicyear')),
                ('finance_fee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='family_invoice_line', to='core.financefee', unique=True)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='core.familyinvoice')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='family_invoice_lines', to='core.student')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_set', to='core.school')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['invoice', 'student'], name='core_family_invoice_9a5f93_idx'),
                ],
            },
        ),
        # --- Repoint QuickBooksCustomerSync from Student to Guardian -----------
        migrations.RemoveField(
            model_name='quickbookscustomersync',
            name='student',
        ),
        migrations.AddField(
            model_name='quickbookscustomersync',
            name='guardian',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.guardian'),
        ),
        # --- Repoint QuickBooksFeeInvoiceSync to become the guardian-level header
        migrations.RemoveIndex(
            model_name='quickbooksfeeinvoicesync',
            name='core_quickb_student_e40d02_idx',
        ),
        migrations.RemoveField(
            model_name='quickbooksfeeinvoicesync',
            name='fee_category',
        ),
        migrations.RemoveField(
            model_name='quickbooksfeeinvoicesync',
            name='fee_particulars',
        ),
        migrations.RemoveField(
            model_name='quickbooksfeeinvoicesync',
            name='finance_fee',
        ),
        migrations.RemoveField(
            model_name='quickbooksfeeinvoicesync',
            name='student',
        ),
        migrations.AddField(
            model_name='quickbooksfeeinvoicesync',
            name='guardian',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.guardian'),
        ),
        migrations.AddField(
            model_name='quickbooksfeeinvoicesync',
            name='family_invoice',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='qb_invoice_sync', to='core.familyinvoice'),
        ),
        migrations.AlterField(
            model_name='quickbooksfeeinvoicesync',
            name='sync_status',
            field=models.CharField(choices=[('draft', 'Draft'), ('synced', 'Synced to QuickBooks'), ('failed', 'Sync Failed'), ('cancelled', 'Cancelled'), ('outdated', 'Legacy - superseded by guardian invoicing')], default='draft', max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name='quickbooksfeeinvoicesync',
            unique_together={('tenant', 'guardian', 'academic_year'), ('tenant', 'quickbooks_invoice_id')},
        ),
        migrations.AddIndex(
            model_name='quickbooksfeeinvoicesync',
            index=models.Index(fields=['guardian', 'academic_year'], name='core_quickb_guardia_4c8015_idx'),
        ),
        # --- New per-student line rows under the guardian-level header ---------
        migrations.CreateModel(
            name='QuickBooksFeeInvoiceLineSync',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('description', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('qb_line_id', models.CharField(blank=True, max_length=100, null=True)),
                ('sync_status', models.CharField(choices=[('draft', 'Draft'), ('synced', 'Synced to QuickBooks'), ('failed', 'Sync Failed')], default='draft', max_length=20)),
                ('synced_at', models.DateTimeField(blank=True, null=True)),
                ('sync_error', models.TextField(blank=True, null=True)),
                ('finance_fee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qb_invoice_line_syncs', to='core.financefee', unique=True)),
                ('invoice_sync', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='core.quickbooksfeeinvoicesync')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.student')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_set', to='core.school')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['invoice_sync', 'student'], name='core_quickb_invoice_6056fc_idx'),
                ],
                'unique_together': {('tenant', 'finance_fee')},
            },
        ),
    ]
