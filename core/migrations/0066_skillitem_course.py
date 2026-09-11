import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_student_optional_fk_blank'),
    ]

    operations = [
        migrations.AddField(
            model_name='skillitem',
            name='course',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='skill_items',
                to='core.course',
                help_text='Class/level this activity applies to; leave blank to share across all pre-grade levels',
            ),
        ),
    ]
