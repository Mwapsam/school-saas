from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_exam_display_name_exam_exam_code_exam_exam_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attendance',
            name='period_table_entry',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendances',
                to='core.periodentry',
            ),
        ),
    ]
