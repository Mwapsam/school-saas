from django.core.management.base import BaseCommand
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = (
        "Backfill QuickBooksRealmMapping (public schema) from each tenant's "
        "existing QuickBooksIntegration.realm_id. Needed for any tenant that "
        "connected QuickBooks before webhook support existed - "
        "QuickBooksService.connect() only writes this mapping on a *new* "
        "OAuth authorization, so pre-existing connections are never backfilled "
        "automatically."
    )

    def handle(self, *args, **options):
        from core.models import QuickBooksIntegration, QuickBooksRealmMapping

        created, updated, skipped = 0, 0, 0

        for tenant in School.objects.exclude(schema_name="public"):
            with schema_context(tenant.schema_name):
                integration = QuickBooksIntegration.objects.filter(
                    tenant=tenant, is_connected=True,
                ).exclude(realm_id__isnull=True).exclude(realm_id="").first()

            if integration is None:
                skipped += 1
                continue

            with schema_context("public"):
                mapping, was_created = QuickBooksRealmMapping.objects.update_or_create(
                    realm_id=integration.realm_id, defaults={"tenant": tenant},
                )

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"Mapped realm {integration.realm_id} -> {tenant.schema_name} ({tenant.name})"
                ))
            else:
                updated += 1
                self.stdout.write(
                    f"Realm {integration.realm_id} already mapped to {mapping.tenant.schema_name} "
                    f"(refreshed to {tenant.schema_name})"
                )

        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {created}, updated {updated}, skipped {skipped} (no active QuickBooks connection)."
        ))
