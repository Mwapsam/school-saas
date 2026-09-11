from django.core.management.base import BaseCommand, CommandError
from core.services.exceptions import ServiceException
from core.services.tenant_provisioning import (
    create_tenant_superuser,
    provision_school,
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create a new tenant (school) with a domain and optional superuser'

    def add_arguments(self, parser):
        # Required
        parser.add_argument('--name', required=True, help='School name (e.g. "Pinewood School Zambia")')
        parser.add_argument('--code', required=True, help='Unique school code (e.g. PWS002)')
        parser.add_argument('--schema', required=True, help='PostgreSQL schema name, lowercase no spaces (e.g. portal2)')
        parser.add_argument('--domain', required=True, help='Primary domain without protocol (e.g. portal2.pinewoodschoolzambia.com)')

        # Optional school details
        parser.add_argument('--phone', default=None)
        parser.add_argument('--email', default=None)
        parser.add_argument('--website', default=None)
        parser.add_argument('--address', default=None, dest='address_line1')
        parser.add_argument('--city', default=None)
        parser.add_argument('--country-code', default=None, dest='country_code',
                            help='Country code to look up and assign')
        parser.add_argument('--no-active', action='store_false', dest='is_active',
                            help='Create tenant as inactive')

        # Additional domains (comma-separated)
        parser.add_argument('--extra-domains', default=None,
                            help='Comma-separated list of additional (non-primary) domains')

        # Optional superuser
        parser.add_argument('--username', default=None, help='Superuser username (skipped if omitted)')
        parser.add_argument('--user-email', default=None, dest='user_email')
        parser.add_argument('--password', default=None)
        parser.add_argument('--first-name', default='Admin', dest='first_name')
        parser.add_argument('--last-name', default='User', dest='last_name')

    def handle(self, *args, **options):
        # Superuser args validated up front so we fail before creating anything.
        if options['username'] and not options['password']:
            raise CommandError("--password is required when --username is provided.")

        extra_domains = None
        if options['extra_domains']:
            extra_domains = options['extra_domains'].split(',')

        # --- Create School / tenant + domains (schema auto-created & migrated) ---
        try:
            result = provision_school(
                name=options['name'],
                code=options['code'],
                schema_name=options['schema'],
                domain=options['domain'],
                is_active=options['is_active'],
                extra_domains=extra_domains,
                country_code=options['country_code'],
                phone=options['phone'],
                email=options['email'],
                website=options['website'],
                address_line1=options['address_line1'],
                city=options['city'],
            )
        except ServiceException as exc:
            raise CommandError(exc.message) from exc

        school = result.school
        if result.country_warning:
            self.stdout.write(self.style.WARNING(result.country_warning))
        self.stdout.write(self.style.SUCCESS(
            f"Created tenant: {school.name} (schema: {school.schema_name})"
        ))
        if result.primary_domain_created:
            self.stdout.write(self.style.SUCCESS(f"Created primary domain: {options['domain'].strip().lower()}"))
        for extra in result.extra_domains_created:
            self.stdout.write(self.style.SUCCESS(f"Created extra domain: {extra}"))

        # --- Create optional superuser ---
        if options['username']:
            try:
                _, created = create_tenant_superuser(
                    school,
                    username=options['username'],
                    email=options['user_email'],
                    password=options['password'],
                    first_name=options['first_name'],
                    last_name=options['last_name'],
                )
            except ServiceException as exc:
                raise CommandError(exc.message) from exc

            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"Created superuser '{options['username']}' in schema '{school.schema_name}'."
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"User '{options['username']}' already exists in schema '{school.schema_name}' — skipping."
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\nTenant '{school.name}' is ready."
        ))
