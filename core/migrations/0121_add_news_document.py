# Generated migration for adding document field to News model

from django.core.validators import FileExtensionValidator
from django.db import migrations, models
import core.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0120_alter_paymentagreement_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='news',
            name='document',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=core.models.upload_to_news_documents,
                validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
            ),
        ),
    ]
