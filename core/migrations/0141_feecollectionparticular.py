# Per-collection fee particulars (e.g. PTA for one term's collection),
# instantiated from a tenant-wide FeeMasterParticular.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0140_transportroute_description_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeeCollectionParticular',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(help_text="Snapshot of the master particular's name at add time", max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('applicability_rule', models.ForeignKey(blank=True, help_text='Optional student scoping; empty = every student in the collection', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collection_particulars', to='core.feeapplicabilityrule')),
                ('fee_collection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_particulars', to='core.feecollection')),
                ('fine_slab', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collection_particulars', to='core.fineslab')),
                ('master_particular', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='collection_particulars', to='core.feemasterparticular')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_set', to='core.school')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddIndex(
            model_name='feecollectionparticular',
            index=models.Index(fields=['tenant'], name='core_feecp_tenant_idx'),
        ),
        migrations.AddIndex(
            model_name='feecollectionparticular',
            index=models.Index(fields=['fee_collection'], name='core_feecp_fc_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='feecollectionparticular',
            unique_together={('fee_collection', 'master_particular')},
        ),
    ]
