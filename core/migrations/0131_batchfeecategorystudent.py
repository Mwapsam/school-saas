# Generated migration for BatchFeeCategoryStudent model

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0130_rename_core_book_library_c4e7f2_idx_core_book_library_c1f2a1_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BatchFeeCategoryStudent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('batch_fee_category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scoped_students', to='core.batchfeecategory')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.student')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.school')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddIndex(
            model_name='batchfeecategorystudent',
            index=models.Index(fields=['tenant'], name='core_batchf_tenant_idx'),
        ),
        migrations.AddIndex(
            model_name='batchfeecategorystudent',
            index=models.Index(fields=['batch_fee_category'], name='core_batchf_batch_f_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='batchfeecategorystudent',
            unique_together={('batch_fee_category', 'student')},
        ),
    ]
