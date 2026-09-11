# Generated migration for Book.library FK

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0127_library_and_library_staff'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='library',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='books', to='core.library'),
        ),
        migrations.AddIndex(
            model_name='book',
            index=models.Index(fields=['library'], name='core_book_library_c4e7f2_idx'),
        ),
    ]
