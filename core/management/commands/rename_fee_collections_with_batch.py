"""
Cosmetic fix: append the batch name to each FeeCollection.name so staff can tell
apart the ~20 same-named collections a term produces (one per batch).

    "TERM 1 2026 PRIMARY"  ->  "TERM 1 2026 PRIMARY - 3A 2026"

Idempotent: a collection whose name already ends with " - <batch name>" (or
already contains the batch name) is left alone, so the command is safe to re-run.

Nothing functional depends on FeeCollection.name - this only changes the label
shown in dropdowns / lists / PDFs.

Dry run by default. Pass --apply to write.

Usage:
    python manage.py rename_fee_collections_with_batch --tenant <id|schema>
    python manage.py rename_fee_collections_with_batch --tenant <id|schema> --apply
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = "Append the batch name to each FeeCollection.name for disambiguation."

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, required=True,
                            help='School / tenant ID or schema_name')
        parser.add_argument('--apply', action='store_true',
                            help='Write the new names (default: dry run)')

    def handle(self, *args, **options):
        ident = options['tenant']
        school = (
            School.objects.filter(id=ident).first()
            if ident.isdigit() else None
        ) or School.objects.filter(schema_name=ident).first()
        if not school:
            self.stdout.write(self.style.ERROR(f"Tenant '{ident}' not found"))
            return

        apply = options['apply']
        if not apply:
            self.stdout.write(self.style.WARNING("DRY RUN - pass --apply to write changes\n"))

        with schema_context(school.schema_name):
            self._run(school, apply)

    def _run(self, school, apply):
        from core.models import FeeCollection

        collections = (
            FeeCollection.objects.filter(tenant=school)
            .select_related('batch')
            .order_by('name', 'created_at')
        )

        renamed = skipped = no_batch = 0

        for c in collections:
            if not c.batch:
                no_batch += 1
                self.stdout.write(f"  SKIP {str(c.id)[:8]} '{c.name}' - no batch")
                continue

            batch_name = c.batch.name.strip()
            if batch_name and batch_name.lower() in c.name.lower():
                skipped += 1
                continue

            new_name = f"{c.name} - {batch_name}"
            renamed += 1
            self.stdout.write(self.style.SUCCESS(
                f"  {str(c.id)[:8]}  '{c.name}'  ->  '{new_name}'"))

            if not apply:
                continue

            with transaction.atomic():
                c.name = new_name
                c.save(update_fields=['name', 'updated_at'])

        self.stdout.write(
            f"\n  renamed={renamed}  already_ok={skipped}  no_batch={no_batch}")
        if not apply and renamed:
            self.stdout.write(self.style.WARNING("  (dry run - re-run with --apply to write)"))
