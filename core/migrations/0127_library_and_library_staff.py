# Generated migration for Library and LibraryStaff models

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0126_feecollection_term'),
    ]

    operations = [
        migrations.CreateModel(
            name='Library',
            fields=[
                ('id', models.UUIDField(default=None, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('code', models.CharField(blank=True, max_length=50, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.school')),
            ],
            options={},
        ),
        migrations.CreateModel(
            name='LibraryStaff',
            fields=[
                ('id', models.UUIDField(default=None, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='library_assignments', to='core.employee')),
                ('library', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staff_assignments', to='core.library')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.school')),
            ],
            options={},
        ),
        migrations.AddIndex(
            model_name='library',
            index=models.Index(fields=['tenant'], name='core_librar_tenant_e56a4b_idx'),
        ),
        migrations.AddConstraint(
            model_name='library',
            constraint=models.UniqueConstraint(fields=['tenant', 'name'], name='unique_library_name_per_tenant'),
        ),
        migrations.AddIndex(
            model_name='librarystaff',
            index=models.Index(fields=['tenant'], name='core_librar_tenant_7f9e1a_idx'),
        ),
        migrations.AddIndex(
            model_name='librarystaff',
            index=models.Index(fields=['employee'], name='core_librar_employ_8e2f3b_idx'),
        ),
        migrations.AddIndex(
            model_name='librarystaff',
            index=models.Index(fields=['library'], name='core_librar_library_9c3d4f_idx'),
        ),
        migrations.AddConstraint(
            model_name='librarystaff',
            constraint=models.UniqueConstraint(fields=['employee', 'library'], name='unique_employee_library_assignment'),
        ),
    ]
