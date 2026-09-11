"""
Management command to create test academic years for all tenants
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from core.models import School, AcademicYear


class Command(BaseCommand):
    help = 'Create test academic years for all schools/tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-code',
            type=str,
            help='Create academic years for specific school by code',
        )

    def handle(self, *args, **options):
        school_code = options.get('school_code')
        
        if school_code:
            try:
                schools = [School.objects.get(code=school_code)]
                self.stdout.write(f"Creating academic years for school: {school_code}")
            except School.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"School with code '{school_code}' not found")
                )
                return
        else:
            schools = School.objects.all()
            self.stdout.write(f"Creating academic years for {schools.count()} schools")

        current_year = date.today().year
        
        for school in schools:
            self.stdout.write(f"Processing school: {school.name} ({school.code})")
            
            # Create academic years for current, next, and previous year
            academic_years_data = [
                {
                    'name': f'{current_year-1}-{current_year}',
                    'start_date': date(current_year-1, 9, 1),
                    'end_date': date(current_year, 6, 30),
                    'is_active': False,
                    'admission_start_date': date(current_year-1, 1, 1),
                    'admission_end_date': date(current_year-1, 8, 31),
                },
                {
                    'name': f'{current_year}-{current_year+1}',
                    'start_date': date(current_year, 9, 1),
                    'end_date': date(current_year+1, 6, 30),
                    'is_active': True,
                    'admission_start_date': date(current_year, 1, 1),
                    'admission_end_date': date(current_year, 8, 31),
                },
                {
                    'name': f'{current_year+1}-{current_year+2}',
                    'start_date': date(current_year+1, 9, 1),
                    'end_date': date(current_year+2, 6, 30),
                    'is_active': True,
                    'admission_start_date': date(current_year+1, 1, 1),
                    'admission_end_date': date(current_year+1, 8, 31),
                },
            ]
            
            created_count = 0
            for ay_data in academic_years_data:
                academic_year, created = AcademicYear.objects.get_or_create(
                    tenant=school,
                    name=ay_data['name'],
                    defaults=ay_data
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ Created: {academic_year.name}")
                    )
                else:
                    self.stdout.write(f"  - Already exists: {academic_year.name}")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"School {school.code}: {created_count} new academic years created"
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS('Academic year creation completed successfully!')
        )