from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0057_reporttemplate_next_term_start'),
    ]

    operations = [
        migrations.AddField(
            model_name='examscore',
            name='grade_value',
            field=models.ForeignKey(
                blank=True,
                help_text='Selected grade for grade-only exams (maximum_marks=0)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='exam_scores',
                to='core.gradevalue',
            ),
        ),
    ]
