"""Pre-cutover checklist for a tenant's QuickBooks integration.

Run immediately before flipping a school to the production QuickBooks app.
Exits non-zero if any hard check fails.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django_tenants.utils import schema_context

from core.models import School


class Command(BaseCommand):
    help = "Verify a tenant's QuickBooks integration is production-ready."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant id, schema name, or domain")
        parser.add_argument("--allow-sandbox", action="store_true",
                            help="Treat a sandbox environment as a warning, not a failure")

    def handle(self, *args, **options):
        tenant = self._resolve_tenant(options["tenant"])
        self.failures = 0
        self.warnings = 0

        with schema_context(tenant.schema_name):
            from core.models import QuickBooksRealmMapping, CurrencyConfiguration
            from core.services.quickbooks_service import QuickBooksService
            from core.services.quickbooks_fee_sync_service import QuickBooksFeeSync

            svc = QuickBooksService(tenant)
            integration = svc.get_integration()

            self.stdout.write(self.style.HTTP_INFO(
                f"QuickBooks preflight - {tenant.name} ({tenant.schema_name})"
            ))

            if integration is None:
                self._fail("integration", "no QuickBooksIntegration row for this tenant")
                raise CommandError("Preflight aborted: integration not configured")

            self._check(
                "environment",
                integration.environment == "production",
                f"environment is '{integration.environment}'",
                hard=not options["allow_sandbox"],
            )
            self._check(
                "connected", integration.is_connected and not integration.is_token_expired(),
                "not connected or token expired",
            )
            self._check(
                "webhook verifier token",
                bool(getattr(settings, "QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN", "")),
                "QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN is not set",
            )

            expected_redirect = getattr(settings, "BASE_URL", "") + reverse("core:quickbooks_callback")
            self._check(
                "redirect_uri matches BASE_URL",
                integration.redirect_uri == expected_redirect,
                f"stored {integration.redirect_uri!r} != expected {expected_redirect!r}",
            )

            if integration.realm_id:
                with schema_context("public"):
                    mapped = QuickBooksRealmMapping.objects.filter(
                        realm_id=integration.realm_id
                    ).exists()
                self._check("realm mapping", mapped,
                            "no QuickBooksRealmMapping (run backfill_quickbooks_realm_mappings)")
            else:
                self._check("realm mapping", False, "no realm_id on the integration")

            test = svc.test_connection()
            self._check("test_connection", test.get("success"), test.get("message", ""))

            config = QuickBooksFeeSync(tenant).config
            item_id = (config.default_service_item or "").strip()
            if not item_id:
                self._check("default service item", False,
                            "QuickBooksConfiguration.default_service_item is not set")
            else:
                try:
                    ok = QuickBooksFeeSync(tenant).validate_service_item(item_id)
                except Exception as e:  # live call may fail
                    ok = False
                    self.stdout.write(self.style.WARNING(f"  (item lookup errored: {e})"))
                self._check("default service item", ok,
                            f"item id {item_id} is not a Service/NonInventory item in QuickBooks")

            currency = CurrencyConfiguration.get_active_currency(tenant)
            if currency.currency_code and currency.currency_code != "USD":
                self._warn(
                    "currency",
                    f"active currency is {currency.currency_code}; the QuickBooks company's "
                    f"home currency must be {currency.currency_code} or multicurrency must be enabled",
                )

        self.stdout.write("")
        if self.failures:
            raise CommandError(f"Preflight FAILED: {self.failures} hard check(s), {self.warnings} warning(s)")
        self.stdout.write(self.style.SUCCESS(
            f"Preflight passed ({self.warnings} warning(s))"
        ))

    # -- helpers --------------------------------------------------------- #

    def _check(self, name, ok, fail_detail, hard=True):
        if ok:
            self.stdout.write(self.style.SUCCESS(f"  PASS  {name}"))
        elif hard:
            self._fail(name, fail_detail)
        else:
            self._warn(name, fail_detail)

    def _fail(self, name, detail):
        self.failures += 1
        self.stdout.write(self.style.ERROR(f"  FAIL  {name}: {detail}"))

    def _warn(self, name, detail):
        self.warnings += 1
        self.stdout.write(self.style.WARNING(f"  WARN  {name}: {detail}"))

    def _resolve_tenant(self, identifier: str) -> School:
        for lookup in ("id", "schema_name", "domains__domain"):
            try:
                return School.objects.get(**{lookup: identifier})
            except (School.DoesNotExist, ValueError):
                continue
        raise CommandError(f"Tenant not found: {identifier}")
