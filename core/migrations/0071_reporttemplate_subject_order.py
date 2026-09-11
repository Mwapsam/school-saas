from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0070_subject_batch_unique_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='reporttemplate',
            name='subject_order',
            field=models.JSONField(
                default=list,
                help_text='Ordered Subject IDs for the exam-scores table in the PDF',
            ),
        ),
    ]
