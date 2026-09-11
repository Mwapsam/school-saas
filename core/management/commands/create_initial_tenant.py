from django.core.management.base import BaseCommand, CommandError
from core.services.exceptions import ServiceException
from core.services.tenant_provisioning import (
    create_tenant_superuser,
    provision_school,
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Creates an initial tenant and superuser for the system'

    def add_arguments(self, parser):
        # Tenant defaults match the original hardcoded values; overridable.
        parser.add_argument('--name', default='Test School', help='School name')
        parser.add_argument('--code', default='PWS001', help='Unique school code')
        parser.add_argument('--schema', default='test_school', help='PostgreSQL schema name')
        parser.add_argument('--domain', default='localhost', help='Primary domain (dev default: localhost)')

        # Superuser
        parser.add_argument('--username', default='root', help='Superuser username')
        parser.add_argument('--email', default='root@dev.co', help='Superuser email')
        parser.add_argument('--password', default='SecurePass123!', help='Superuser password')
        parser.add_argument('--first-name', default='Sam', help='Superuser first name')
        parser.add_argument('--last-name', default='Mwape', help='Superuser last name')

    def handle(self, *args, **options):
        # Create the tenant + domain. Existing tenant is a warning, not an error,
        # so the command stays idempotent and still ensures the superuser exists.
        try:
            result = provision_school(
                name=options['name'],
                code=options['code'],
                schema_name=options['schema'],
                domain=options['domain'],
                is_active=True,
                allow_existing=True,
            )
        except ServiceException as exc:
            raise CommandError(exc.message) from exc

        school = result.school
        if result.school_created:
            self.stdout.write(self.style.SUCCESS(f"Created tenant: {school.name}"))
            if result.primary_domain_created:
                self.stdout.write(self.style.SUCCESS(f"Created domain: {options['domain'].strip().lower()}"))
        else:
            self.stdout.write(self.style.WARNING(
                f"Tenant with schema_name '{school.schema_name}' already exists: {school.name}"
            ))

        # Ensure the superuser exists in the tenant's schema.
        try:
            _, created = create_tenant_superuser(
                school,
                username=options['username'],
                email=options['email'],
                password=options['password'],
                first_name=options['first_name'],
                last_name=options['last_name'],
            )
        except ServiceException as exc:
            raise CommandError(exc.message) from exc

        if created:
            self.stdout.write(self.style.SUCCESS(
                f"Created superuser: {options['username']} for tenant {school.name}"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Superuser {options['username']} already exists in schema {school.schema_name}"
            ))
