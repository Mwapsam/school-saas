"""
Management command to seed default grading scales for a tenant.

Usage:
    python manage.py seed_grading_scales --tenant=<tenant_id>
    python manage.py seed_grading_scales --all
"""

from django.core.management.base import BaseCommand
from core.models import School, GradingScale, GradeValue


class Command(BaseCommand):
    help = 'Seed default grading scales for tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Tenant ID to seed grading scales for'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Seed grading scales for all tenants'
        )

    def handle(self, *args, **options):
        if options['all']:
            tenants = School.objects.all()
            self.stdout.write(f"Seeding grading scales for {tenants.count()} tenants...")
        elif options['tenant']:
            try:
                tenant = School.objects.get(id=options['tenant'])
                tenants = [tenant]
            except School.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Tenant with ID {options['tenant']} not found"))
                return
        else:
            self.stdout.write(self.style.ERROR("Please specify --tenant=<id> or --all"))
            return

        for tenant in tenants:
            self.stdout.write(f"\nSeeding grading scales for tenant: {tenant.name}")
            self.seed_tenant_grading_scales(tenant)

        self.stdout.write(self.style.SUCCESS("\n✓ Grading scales seeded successfully!"))

    def seed_tenant_grading_scales(self, tenant):
        """Seed all default grading scales for a tenant"""

        # 1. Letter Grades (A-F)
        letter_scale, created = GradingScale.objects.get_or_create(
            tenant=tenant,
            code='LETTER_GRADES',
            defaults={
                'name': 'Letter Grades',
                'scale_type': 'LETTER',
                'description': 'Standard A-F letter grading system',
                'is_active': True,
                'is_default': True,  # Set as default
                'report_layout': 'FULL_ACADEMIC',
            }
        )
        if created:
            self.stdout.write(f"  Created: {letter_scale.name}")
            # Create grade values
            letter_grades = [
                ('A', 'A', 90, 100, 4.0, 1, True, '#4CAF50'),
                ('B', 'B', 80, 89, 3.0, 2, True, '#8BC34A'),
                ('C', 'C', 70, 79, 2.0, 3, True, '#FFC107'),
                ('D', 'D', 60, 69, 1.0, 4, True, '#FF9800'),
                ('E', 'E', 50, 59, 0.5, 5, False, '#FF5722'),
                ('F', 'F', 0, 49, 0.0, 6, False, '#F44336'),
            ]
            for name, code, min_pct, max_pct, gpa, order, passing, color in letter_grades:
                GradeValue.objects.create(
                    tenant=tenant,
                    grading_scale=letter_scale,
                    name=name,
                    code=code,
                    min_percentage=min_pct,
                    max_percentage=max_pct,
                    gpa_value=gpa,
                    display_order=order,
                    is_passing=passing,
                    color_code=color
                )

        # 2. Descriptive Grades
        descriptive_scale, created = GradingScale.objects.get_or_create(
            tenant=tenant,
            code='DESCRIPTIVE_GRADES',
            defaults={
                'name': 'Descriptive Grades',
                'scale_type': 'DESCRIPTIVE',
                'description': 'Very Good, Good, Satisfactory, Weak grading',
                'is_active': True,
                'is_default': False,
                'report_layout': 'FULL_ACADEMIC',
            }
        )
        if created:
            self.stdout.write(f"  Created: {descriptive_scale.name}")
            descriptive_grades = [
                ('Very Good', 'VERY_GOOD', 90, 100, None, 1, True, '#4CAF50'),
                ('Good', 'GOOD', 75, 89, None, 2, True, '#8BC34A'),
                ('Satisfactory', 'SATISFACTORY', 50, 74, None, 3, True, '#FFC107'),
                ('Weak', 'WEAK', 35, 49, None, 4, False, '#FF9800'),
                ('Very Weak', 'VERY_WEAK', 0, 34, None, 5, False, '#F44336'),
            ]
            for name, code, min_pct, max_pct, gpa, order, passing, color in descriptive_grades:
                GradeValue.objects.create(
                    tenant=tenant,
                    grading_scale=descriptive_scale,
                    name=name,
                    code=code,
                    min_percentage=min_pct,
                    max_percentage=max_pct,
                    gpa_value=gpa,
                    display_order=order,
                    is_passing=passing,
                    color_code=color
                )

        # 2b. Four-point Letter scale (Grade 1–2 / Simple Academic)
        simple_scale, created = GradingScale.objects.get_or_create(
            tenant=tenant,
            code='LETTER_4POINT',
            defaults={
                'name': 'Lower School (Grade 1–2)',
                'scale_type': 'LETTER',
                'description': '4-point A–D scale for the Simple Academic report',
                'is_active': True,
                'is_default': False,
                'report_layout': 'SIMPLE_ACADEMIC',
            }
        )
        if created:
            self.stdout.write(f"  Created: {simple_scale.name}")
            four_point = [
                ('A', 'A', 80, 100, None, 1, True, '#4CAF50'),
                ('B', 'B', 60, 79, None, 2, True, '#8BC34A'),
                ('C', 'C', 50, 59, None, 3, True, '#FFC107'),
                ('D', 'D', 0, 49, None, 4, False, '#FF5722'),
            ]
            for name, code, min_pct, max_pct, gpa, order, passing, color in four_point:
                GradeValue.objects.create(
                    tenant=tenant,
                    grading_scale=simple_scale,
                    name=name,
                    code=code,
                    min_percentage=min_pct,
                    max_percentage=max_pct,
                    gpa_value=gpa,
                    display_order=order,
                    is_passing=passing,
                    color_code=color
                )

        # 3. Skill Levels (for early childhood)
        skill_scale, created = GradingScale.objects.get_or_create(
            tenant=tenant,
            code='SKILL_LEVELS',
            defaults={
                'name': 'Skill Development Levels',
                'scale_type': 'LEVEL',
                'description': 'Not Yet, Beginning, Satisfactory, Good - for skills assessment',
                'is_active': True,
                'is_default': False,
                'report_layout': 'SKILLS',
            }
        )
        if created:
            self.stdout.write(f"  Created: {skill_scale.name}")
            skill_levels = [
                ('Good', 'GOOD', None, None, None, 1, True, '#4CAF50'),
                ('Satisfactory', 'SATISFACTORY', None, None, None, 2, True, '#8BC34A'),
                ('Beginning', 'BEGINNING', None, None, None, 3, True, '#FFC107'),
                ('Not Yet', 'NOT_YET', None, None, None, 4, True, '#FF9800'),
            ]
            for name, code, min_pct, max_pct, gpa, order, passing, color in skill_levels:
                GradeValue.objects.create(
                    tenant=tenant,
                    grading_scale=skill_scale,
                    name=name,
                    code=code,
                    min_percentage=min_pct,
                    max_percentage=max_pct,
                    gpa_value=gpa,
                    display_order=order,
                    is_passing=passing,
                    color_code=color
                )

        # 4. Binary (Y/N)
        binary_scale, created = GradingScale.objects.get_or_create(
            tenant=tenant,
            code='BINARY_YN',
            defaults={
                'name': 'Binary (Y/N)',
                'scale_type': 'BINARY',
                'description': 'Simple Yes/No or Pass/Fail grading',
                'is_active': True,
                'is_default': False
            }
        )
        if created:
            self.stdout.write(f"  Created: {binary_scale.name}")
            binary_values = [
                ('Y', 'YES', None, None, None, 1, True, '#4CAF50'),
                ('N', 'NO', None, None, None, 2, False, '#F44336'),
            ]
            for name, code, min_pct, max_pct, gpa, order, passing, color in binary_values:
                GradeValue.objects.create(
                    tenant=tenant,
                    grading_scale=binary_scale,
                    name=name,
                    code=code,
                    min_percentage=min_pct,
                    max_percentage=max_pct,
                    gpa_value=gpa,
                    display_order=order,
                    is_passing=passing,
                    color_code=color
                )

        # 5. Numeric Percentage
        numeric_scale, created = GradingScale.objects.get_or_create(
            tenant=tenant,
            code='NUMERIC_PERCENTAGE',
            defaults={
                'name': 'Numeric Percentage',
                'scale_type': 'NUMERIC',
                'description': 'Direct numeric marks (0-100%)',
                'is_active': True,
                'is_default': False
            }
        )
        if created:
            self.stdout.write(f"  Created: {numeric_scale.name}")
            # For numeric, we don't create fixed grade values
            # The actual percentage is used directly

        self.stdout.write(self.style.SUCCESS(f"  ✓ Seeded {tenant.name}"))