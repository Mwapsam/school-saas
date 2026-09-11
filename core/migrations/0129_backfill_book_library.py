# Data migration to backfill Book.library with a default "Main Library" per tenant

from django.db import migrations


def backfill_book_library(apps, schema_editor):
    """
    For each tenant that has existing Book rows, create or reuse a Library named
    "Main Library" (code="MAIN") and backfill all Books with library_id=NULL to it.
    Tenants with no Books are skipped (a small school might not use library yet).
    """
    School = apps.get_model('core', 'School')
    Book = apps.get_model('core', 'Book')
    Library = apps.get_model('core', 'Library')

    for tenant in School.objects.all():
        # Only backfill if tenant has at least one Book
        if not Book.objects.filter(tenant=tenant).exists():
            continue

        # Get or create the default library for this tenant
        library, created = Library.objects.get_or_create(
            tenant=tenant,
            name='Main Library',
            defaults={'code': 'MAIN', 'is_active': True}
        )

        # Backfill all Books in this tenant that don't yet have a library assigned
        Book.objects.filter(tenant=tenant, library__isnull=True).update(library=library)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0128_book_library'),
    ]

    operations = [
        migrations.RunPython(backfill_book_library, noop),
    ]
