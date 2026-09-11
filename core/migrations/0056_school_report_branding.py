import core.models
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_report_format_and_skills'),
    ]

    operations = [
        migrations.AddField(
            model_name='school',
            name='signature',
            field=models.ImageField(
                blank=True, null=True,
                storage=core.models.public_storage,
                upload_to=core.models.school_signature_path,
                validators=[django.core.validators.FileExtensionValidator(
                    allowed_extensions=['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'])],
            ),
        ),
        migrations.AddField(
            model_name='school',
            name='report_title',
            field=models.CharField(default='ASSESSMENT REPORT', max_length=255),
        ),
        migrations.AddField(
            model_name='school',
            name='footer_quote',
            field=models.TextField(
                default='Pro 22:6 KJV Train up a child in the way he should go: and when he is old, he will not depart from it.'
            ),
        ),
        migrations.AddField(
            model_name='school',
            name='signature_title',
            field=models.CharField(default='Head of School', max_length=100),
        ),
    ]
