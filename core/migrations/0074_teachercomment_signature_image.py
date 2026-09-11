from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0073_teachercomment'),
    ]

    operations = [
        migrations.AddField(
            model_name='teachercomment',
            name='signature_image',
            field=models.TextField(blank=True, default=''),
        ),
    ]
