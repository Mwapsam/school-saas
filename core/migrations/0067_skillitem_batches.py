from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0066_skillitem_course'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='skillitem',
            name='course',
        ),
        migrations.AddField(
            model_name='skillitem',
            name='batches',
            field=models.ManyToManyField(
                blank=True,
                related_name='skill_items',
                to='core.batch',
                help_text='Classes/batches this activity applies to; leave empty to share across all pre-grade classes',
            ),
        ),
    ]
