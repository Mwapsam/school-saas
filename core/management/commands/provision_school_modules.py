"""
Management command to initialize SchoolModule records for schools.

Usage:
    # Provision all modules for a specific school (by code or name)
    python manage.py provision_school_modules --school-code ABC123
    python manage.py provision_school_modules --school-name "Pinewood School"

    # Provision modules for all schools in the system
    python manage.py provision_school_modules --all

    # Provision with specific enabled/disabled modules
    python manage.py provision_school_modules --school-code ABC123 --enable hr,finance --disable hostel,transport

    # Dry run to see what would be created
    python manage.py provision_school_modules --school-code ABC123 --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from core.models import School, SchoolModule
from core.modules import MODULES, is_module_required


class Command(BaseCommand):
    help = "Initialize SchoolModule records to enable/disable product modules per school"

    def add_arguments(self, parser):
        parser.add_argument(
            "--school-code",
            type=str,
            help="School code (unique identifier) to provision"
        )
        parser.add_argument(
            "--school-name",
            type=str,
            help="School name to provision (used if code not provided)"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Provision all schools in the system"
        )
        parser.add_argument(
            "--enable",
            type=str,
            help="Comma-separated list of modules to enable (default: all except disabled)"
        )
        parser.add_argument(
            "--disable",
            type=str,
            help="Comma-separated list of modules to disable"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating"
        )

    def handle(self, *args, **options):
        school_code = options.get("school_code")
        school_name = options.get("school_name")
        all_schools = options.get("all", False)
        enable_list = options.get("enable", "").split(",") if options.get("enable") else []
        disable_list = options.get("disable", "").split(",") if options.get("disable") else []
        dry_run = options.get("dry_run", False)

        # Parse enable/disable lists
        enable_list = [m.strip() for m in enable_list if m.strip()]
        disable_list = [m.strip() for m in disable_list if m.strip()]

        # Validate module keys
        for module_key in enable_list + disable_list:
            if module_key not in MODULES:
                raise CommandError(f"Unknown module: {module_key}")

        # If both enable and disable are specified, validate no overlap
        if enable_list and disable_list:
            overlap = set(enable_list) & set(disable_list)
            if overlap:
                raise CommandError(
                    f"Modules cannot be both enabled and disabled: {overlap}"
                )

        # Determine which schools to provision
        schools = []
        if all_schools:
            schools = list(School.objects.all())
        elif school_code:
            try:
                schools = [School.objects.get(code=school_code)]
            except School.DoesNotExist:
                raise CommandError(f"School with code '{school_code}' not found")
        elif school_name:
            schools = list(School.objects.filter(name=school_name))
            if not schools:
                raise CommandError(f"No schools with name '{school_name}' found")
        else:
            raise CommandError(
                "Specify --school-code, --school-name, or --all"
            )

        self.stdout.write(
            self.style.SUCCESS(f"Provisioning modules for {len(schools)} school(s)")
        )

        total_created = 0
        total_skipped = 0

        for school in schools:
            self.stdout.write(f"\nProcessing {school.name} ({school.code})...")

            # Determine enabled/disabled for each module
            for module_key in MODULES.keys():
                # Required modules are always enabled
                if is_module_required(module_key):
                    enabled = True
                # Explicit enable/disable lists override defaults
                elif enable_list:
                    enabled = module_key in enable_list
                elif disable_list:
                    enabled = module_key not in disable_list
                # Default: enable all modules
                else:
                    enabled = True

                if dry_run:
                    status = "✓ enabled" if enabled else "✗ disabled"
                    self.stdout.write(f"  {module_key}: {status} (dry run)")
                else:
                    obj, created = SchoolModule.objects.get_or_create(
                        school=school,
                        module=module_key,
                        defaults={"enabled": enabled}
                    )
                    if created:
                        status = "✓ enabled" if enabled else "✗ disabled"
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ Created: {module_key} [{status}]"
                            )
                        )
                        total_created += 1
                    else:
                        status = "✓ enabled" if obj.enabled else "✗ disabled"
                        self.stdout.write(f"  - Exists: {module_key} [{status}]")
                        total_skipped += 1

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Done! Created {total_created} new module records, "
                    f"skipped {total_skipped} existing ones."
                )
            )
        else:
            self.stdout.write(self.style.WARNING("\n(Dry run — no changes made)"))
