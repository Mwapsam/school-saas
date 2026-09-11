from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_subject_employee'),
    ]

    operations = [
        migrations.AddField(
            model_name='batch',
            name='class_teachers',
            field=models.ManyToManyField(
                blank=True,
                related_name='class_teacher_batches',
                to='core.employee',
                help_text='All class teachers responsible for this batch',
            ),
        ),
    ]
