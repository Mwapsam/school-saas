"""
Management command to seed sample admission applications for testing
"""
from django.core.management.base import BaseCommand
from core.models import School, AdmissionApplication, Course
from datetime import date, timedelta
import random


class Command(BaseCommand):
    help = 'Seed sample admission applications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-code',
            type=str,
            default='demo',
            help='Seed data for specific school by code (default: demo)',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=25,
            help='Number of applications to create (default: 25)',
        )

    def handle(self, *args, **options):
        school_code = options.get('school_code')
        count = options.get('count')

        try:
            school = School.objects.get(code=school_code)
            self.stdout.write(f"Seeding applications for school: {school.name} ({school.code})")
        except School.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"School with code '{school_code}' not found")
            )
            return

        # Get courses for the school
        courses = list(Course.objects.filter(tenant=school)[:5])
        if not courses:
            self.stdout.write(
                self.style.ERROR("No courses found. Run 'setup_basic_data' first.")
            )
            return

        self.stdout.write(f"Creating {count} applications...")
        self.create_applications(school, courses, count)

        self.stdout.write(
            self.style.SUCCESS('\nAdmission applications seeding completed successfully!')
        )

    def create_applications(self, school, courses, count):
        """Create sample admission applications"""

        first_names = [
            'Alice', 'Benjamin', 'Chloe', 'David', 'Emma', 'Frank', 'Grace', 'Henry',
            'Iris', 'Jacob', 'Kimberly', 'Liam', 'Mia', 'Noah', 'Olivia', 'Patrick',
            'Quinn', 'Rachel', 'Samuel', 'Tina', 'Ulysses', 'Victoria', 'William', 'Xander',
            'Yara', 'Zachary'
        ]

        last_names = [
            'Banda', 'Chawama', 'Dube', 'Elumo', 'Farah', 'Gaba', 'Handako', 'Igwe',
            'Juma', 'Kamau', 'Lamba', 'Manda', 'Nkosi', 'Ouma', 'Phiri', 'Quisumbing',
            'Raheem', 'Simone', 'Themba', 'Uddin', 'Vance', 'Wandira', 'Xavier', 'Yates',
            'Zuma'
        ]

        guardian_names = [
            'Mr. {0} {1}', 'Mrs. {0} {1}', 'Ms. {0} {1}', 'Dr. {0} {1}', 'Prof. {0} {1}'
        ]

        statuses = ['pending', 'under_review', 'approved', 'rejected', 'on_hold']

        # Date range for applications (last 3 months)
        today = date.today()
        start_date = today - timedelta(days=90)

        # Get existing app count to ensure unique numbering
        existing_count = AdmissionApplication.objects.filter(tenant=school).count()

        created_count = 0
        for i in range(count):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)

            # Generate application number - start from existing count
            app_number = f"APP{today.year}{str(existing_count + i + 1).zfill(4)}"

            # Random dates within the range
            application_date = start_date + timedelta(days=random.randint(0, 89))

            # Date of birth (students aged 5-18)
            dob_year = today.year - random.randint(5, 18)
            dob_month = random.randint(1, 12)
            dob_day = random.randint(1, 28)  # Safe for all months
            dob = date(dob_year, dob_month, dob_day)

            # Guardian information
            guardian_name_template = random.choice(guardian_names)
            guardian_first = random.choice(first_names)
            guardian_last = random.choice(last_names)
            guardian_name = guardian_name_template.format(guardian_first, guardian_last)

            guardian_email = f"{guardian_first.lower()}.{guardian_last.lower()}@school.local"
            guardian_phone = f"+26097{random.randint(1000000, 9999999)}"

            # Status distribution: more pending than others
            if i < count * 0.4:
                status = 'pending'
            elif i < count * 0.6:
                status = 'under_review'
            elif i < count * 0.8:
                status = 'approved'
            else:
                status = random.choice(['on_hold', 'rejected'])

            app = AdmissionApplication.objects.create(
                tenant=school,
                application_number=app_number,
                first_name=first_name,
                middle_name=random.choice(['', '', '', random.choice(first_names)]),  # 25% have middle name
                last_name=last_name,
                date_of_birth=dob,
                gender=random.choice(['male', 'female']),
                course_applied=random.choice(courses),
                guardian_name=guardian_name,
                guardian_phone=guardian_phone,
                guardian_email=guardian_email,
                address=f"Plot {random.randint(1, 999)}, {random.choice(['Lusaka', 'Ndola', 'Kitwe', 'Livingstone', 'Kabwe'])}",
                status=status,
                application_date=application_date,
                remarks=random.choice([
                    'Strong academic background',
                    'Good school report',
                    'Awaiting further documents',
                    'Interview completed',
                    'Under review by admissions committee',
                    '',
                    ''
                ]) if status != 'pending' else '',
            )
            created_count += 1

            if (i + 1) % 5 == 0:
                self.stdout.write(f"  Created {i + 1}/{count} applications...")

        self.stdout.write(f"  ✓ Successfully created {created_count} admission applications")

        # Print status summary
        status_counts = AdmissionApplication.objects.filter(tenant=school).values('status').distinct()
        self.stdout.write("\nStatus breakdown:")
        for status_choice in statuses:
            count = AdmissionApplication.objects.filter(tenant=school, status=status_choice).count()
            if count > 0:
                self.stdout.write(f"  - {status_choice}: {count}")
