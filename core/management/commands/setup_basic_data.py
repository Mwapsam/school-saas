"""
Management command to set up basic data for the admission system
This includes academic years, countries, and student categories
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from core.models import School, AcademicYear, Country, StudentCategory, Course


class Command(BaseCommand):
    help = 'Set up basic data required for the admission system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-code',
            type=str,
            help='Set up data for specific school by code',
        )

    def handle(self, *args, **options):
        school_code = options.get('school_code')
        
        # Set up countries first (these are global)
        self.setup_countries()
        
        # Get schools to set up
        if school_code:
            try:
                schools = [School.objects.get(code=school_code)]
                self.stdout.write(f"Setting up data for school: {school_code}")
            except School.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"School with code '{school_code}' not found")
                )
                return
        else:
            schools = School.objects.all()
            if not schools.exists():
                self.stdout.write(
                    self.style.WARNING("No schools found. Please create a school first.")
                )
                return
            self.stdout.write(f"Setting up data for {schools.count()} schools")

        # Set up data for each school
        for school in schools:
            self.stdout.write(f"\nProcessing school: {school.name} ({school.code})")
            self.setup_academic_years(school)
            self.setup_courses(school)
            self.setup_student_categories(school)
        
        self.stdout.write(
            self.style.SUCCESS('\nBasic data setup completed successfully!')
        )

    def setup_countries(self):
        """Set up basic countries data"""
        self.stdout.write("Setting up countries...")
        
        countries_data = [
            {'name': 'Zambia', 'code': 'ZM'},
            {'name': 'South Africa', 'code': 'ZA'},
            {'name': 'Kenya', 'code': 'KE'},
            {'name': 'Tanzania', 'code': 'TZ'},
            {'name': 'Uganda', 'code': 'UG'},
            {'name': 'Botswana', 'code': 'BW'},
            {'name': 'Namibia', 'code': 'NA'},
            {'name': 'Zimbabwe', 'code': 'ZW'},
            {'name': 'Malawi', 'code': 'MW'},
            {'name': 'Mozambique', 'code': 'MZ'},
            {'name': 'United Kingdom', 'code': 'GB'},
            {'name': 'United States', 'code': 'US'},
            {'name': 'Canada', 'code': 'CA'},
            {'name': 'Australia', 'code': 'AU'},
            {'name': 'India', 'code': 'IN'},
            {'name': 'Other', 'code': 'XX'},
        ]
        
        created_count = 0
        for country_data in countries_data:
            country, created = Country.objects.get_or_create(
                code=country_data['code'],
                defaults={'name': country_data['name']}
            )
            if created:
                created_count += 1
                self.stdout.write(f"  ✓ Created country: {country.name}")
            else:
                # Update name if it differs
                if country.name != country_data['name']:
                    country.name = country_data['name']
                    country.save()
                    self.stdout.write(f"  ↻ Updated country: {country.name}")
        
        self.stdout.write(f"Countries: {created_count} new, {Country.objects.count()} total")

    def setup_academic_years(self, school):
        """Set up academic years for a school"""
        self.stdout.write("  Setting up academic years...")
        
        current_year = date.today().year
        
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
                self.stdout.write(f"    ✓ Created: {academic_year.name}")
            else:
                self.stdout.write(f"    - Exists: {academic_year.name}")
        
        self.stdout.write(f"  Academic years: {created_count} new")

    def setup_courses(self, school):
        """Set up basic courses for a school"""
        self.stdout.write("  Setting up courses...")
        
        courses_data = [
            {'course_name': 'Nursery', 'code': 'NUR', 'section_name': 'Early Years'},
            {'course_name': 'Reception', 'code': 'REC', 'section_name': 'Early Years'},
            {'course_name': 'Grade 1', 'code': 'G1', 'section_name': 'Primary'},
            {'course_name': 'Grade 2', 'code': 'G2', 'section_name': 'Primary'},
            {'course_name': 'Grade 3', 'code': 'G3', 'section_name': 'Primary'},
            {'course_name': 'Grade 4', 'code': 'G4', 'section_name': 'Primary'},
            {'course_name': 'Grade 5', 'code': 'G5', 'section_name': 'Primary'},
            {'course_name': 'Grade 6', 'code': 'G6', 'section_name': 'Primary'},
            {'course_name': 'Grade 7', 'code': 'G7', 'section_name': 'Primary'},
            {'course_name': 'Grade 8', 'code': 'G8', 'section_name': 'Secondary'},
            {'course_name': 'Grade 9', 'code': 'G9', 'section_name': 'Secondary'},
            {'course_name': 'Grade 10', 'code': 'G10', 'section_name': 'Secondary'},
            {'course_name': 'Grade 11', 'code': 'G11', 'section_name': 'Secondary'},
            {'course_name': 'Grade 12', 'code': 'G12', 'section_name': 'Secondary'},
        ]
        
        created_count = 0
        for course_data in courses_data:
            course, created = Course.objects.get_or_create(
                tenant=school,
                code=course_data['code'],
                defaults={
                    'course_name': course_data['course_name'],
                    'section_name': course_data['section_name'],
                    'is_deleted': False
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f"    ✓ Created: {course.course_name} ({course.code})")
            else:
                self.stdout.write(f"    - Exists: {course.course_name} ({course.code})")
        
        self.stdout.write(f"  Courses: {created_count} new")

    def setup_student_categories(self, school):
        """Set up student categories for a school"""
        self.stdout.write("  Setting up student categories...")
        
        categories_data = [
            'Regular Student',
            'International Student',
            'Staff Child',
            'Scholarship Student',
            'Transfer Student',
            'Special Needs Student',
        ]
        
        created_count = 0
        for category_name in categories_data:
            category, created = StudentCategory.objects.get_or_create(
                tenant=school,
                name=category_name,
                defaults={'is_deleted': False}
            )
            
            if created:
                created_count += 1
                self.stdout.write(f"    ✓ Created: {category.name}")
            else:
                self.stdout.write(f"    - Exists: {category.name}")
        
        self.stdout.write(f"  Student categories: {created_count} new")