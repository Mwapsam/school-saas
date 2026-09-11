# Generated manually for adding grading_scale to Exam model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_grading_scale_system'),
    ]

    operations = [
        migrations.AddField(
            model_name='exam',
            name='grading_scale',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='exams',
                to='core.gradingscale',
                help_text='Grading scale for this exam (overrides subject default)'
            ),
        ),
    ]