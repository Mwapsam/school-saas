from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0068_alter_employee_employee_category_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='extendedadmissionapplication',
            name='admitted_student',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='admission_applications',
                to='core.student',
            ),
        ),
    ]
