"""Management command to populate Weekday table with standard days of the week"""
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Weekday, School


WEEKDAYS = [
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday'),
]


class Command(BaseCommand):
    help = 'Populate Weekday table with standard days of the week for all tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Populate for specific tenant (by schema_name)',
        )

    def handle(self, *args, **options):
        tenant_filter = options.get('tenant')

        # Get all active tenants (Schools)
        if tenant_filter:
            tenants = School.objects.filter(schema_name=tenant_filter)
        else:
            tenants = School.objects.all()

        if not tenants.exists():
            self.stdout.write(
                self.style.WARNING('No tenants found to populate weekdays for.')
            )
            return

        for tenant in tenants:
            self.stdout.write(f'Processing tenant: {tenant.name} ({tenant.schema_name})')

            with transaction.atomic():
                created_count = 0
                for day_of_week, weekday_name in WEEKDAYS:
                    weekday, created = Weekday.objects.get_or_create(
                        tenant=tenant,
                        day_of_week=day_of_week,
                        defaults={'weekday': weekday_name, 'is_deleted': False}
                    )
                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ Created: {weekday_name} (day_of_week={day_of_week})'
                            )
                        )
                    else:
                        self.stdout.write(
                            f'  - Already exists: {weekday_name}'
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Completed for {tenant.name}: {created_count} new weekdays created\n'
                )
            )

        self.stdout.write(
            self.style.SUCCESS('✓ All tenants populated with weekdays')
        )
