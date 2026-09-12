"""
Management command to seed sample student, guardian, and employee data for testing
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from core.models import School, User, Student, Guardian, StudentGuardianRelation, Employee
import uuid


class Command(BaseCommand):
    help = 'Seed sample student, guardian, and employee data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--school-code',
            type=str,
            default='demo',
            help='Seed data for specific school by code (default: demo)',
        )
        parser.add_argument(
            '--students',
            type=int,
            default=3,
            help='Number of sample students to create (default: 3)',
        )
        parser.add_argument(
            '--employees',
            type=int,
            default=2,
            help='Number of sample employees to create (default: 2)',
        )

    def handle(self, *args, **options):
        school_code = options.get('school_code')
        num_students = options.get('students')
        num_employees = options.get('employees')

        try:
            school = School.objects.get(code=school_code)
            self.stdout.write(f"Seeding data for school: {school.name} ({school.code})")
        except School.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"School with code '{school_code}' not found")
            )
            return

        # Get country for Zambia
        country_id = 1  # Assuming country ID 1 is Zambia from setup_basic_data

        self.stdout.write(f"\nCreating {num_students} students...")
        student_ids = self.create_students(school, country_id, num_students)

        self.stdout.write(f"\nCreating guardians...")
        self.create_guardians(school, country_id, student_ids)

        self.stdout.write(f"\nCreating {num_employees} employees...")
        self.create_employees(school, country_id, num_employees)

        self.stdout.write(
            self.style.SUCCESS('\nSample data seeding completed successfully!')
        )

    def create_students(self, school, country_id, count):
        """Create sample students with users"""
        student_data = [
            {
                'admission_no': 'ST001',
                'first_name': 'John',
                'last_name': 'Doe',
                'username': 'student1',
                'email': 'john.doe@school.local',
                'dob': '2010-05-20',
                'gender': 'male',
            },
            {
                'admission_no': 'ST002',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'username': 'student2',
                'email': 'jane.smith@school.local',
                'dob': '2010-08-15',
                'gender': 'female',
            },
            {
                'admission_no': 'ST003',
                'first_name': 'David',
                'last_name': 'Banda',
                'username': 'student3',
                'email': 'david.banda@school.local',
                'dob': '2011-01-30',
                'gender': 'male',
            },
        ]

        student_ids = []
        for i, data in enumerate(student_data[:count]):
            # Create user
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'password': make_password('password123'),
                    'is_active': True,
                }
            )
            if created:
                user.tenants.add(school)

            # Create student
            student = Student.objects.create(
                tenant=school,
                admission_no=data['admission_no'],
                class_roll_no=f'R{i+1:03d}',
                admission_date='2026-01-15',
                first_name=data['first_name'],
                last_name=data['last_name'],
                date_of_birth=data['dob'],
                gender=data['gender'],
                blood_group=['O+', 'AB+', 'B+'][i % 3],
                birth_place='Lusaka',
                nationality_id=country_id,
                country_id=country_id,
                email=data['email'],
                phone1=f'+26097123456{i}',
                is_active=True,
                user=user,
            )
            student_ids.append(student.id)
            self.stdout.write(f"  ✓ Created student: {student.full_name} ({student.admission_no})")

        return student_ids

    def create_guardians(self, school, country_id, student_ids):
        """Create sample guardians and link them to students"""
        guardian_data = [
            {
                'first_name': 'Jane',
                'last_name': 'Doe',
                'relation': 'Parent',
                'email': 'jane.doe@school.local',
                'phone': '+260971234560',
                'occupation': 'Engineer',
            },
            {
                'first_name': 'Robert',
                'last_name': 'Smith',
                'relation': 'Parent',
                'email': 'robert.smith@school.local',
                'phone': '+260971234561',
                'occupation': 'Doctor',
            },
            {
                'first_name': 'Moses',
                'last_name': 'Banda',
                'relation': 'Parent',
                'email': 'moses.banda@school.local',
                'phone': '+260971234562',
                'occupation': 'Teacher',
            },
        ]

        for i, (student_id, guardian_info) in enumerate(zip(student_ids, guardian_data)):
            guardian = Guardian.objects.create(
                tenant=school,
                first_name=guardian_info['first_name'],
                last_name=guardian_info['last_name'],
                relation=guardian_info['relation'],
                email=guardian_info['email'],
                mobile_phone=guardian_info['phone'],
                occupation=guardian_info['occupation'],
                country_id=country_id,
                dob='1980-03-10',
                income=25000.00,
                education="Bachelor's Degree",
                is_active=True,
            )

            # Link guardian to student
            StudentGuardianRelation.objects.create(
                tenant=school,
                school_id=school.id,
                student_id=student_id,
                guardian=guardian,
                relation=guardian_info['relation'],
                is_immediate_contact=True,
            )

            self.stdout.write(f"  ✓ Created guardian: {guardian.first_name} {guardian.last_name}")

    def create_employees(self, school, country_id, count):
        """Create sample employees (teachers and staff)"""
        employee_data = [
            {
                'employee_number': 'EMP001',
                'first_name': 'Mary',
                'last_name': 'Banda',
                'username': 'teacher1',
                'email': 'mary.banda@school.local',
                'job_title': 'Mathematics Teacher',
                'qualification': 'Bachelor of Education (Mathematics)',
                'dob': '1985-06-20',
                'is_teaching_staff': True,
            },
            {
                'employee_number': 'EMP002',
                'first_name': 'Peter',
                'last_name': 'Mukwita',
                'username': 'teacher2',
                'email': 'peter.mukwita@school.local',
                'job_title': 'English Teacher',
                'qualification': 'Bachelor of Arts (English)',
                'dob': '1990-09-15',
                'is_teaching_staff': True,
            },
        ]

        for i, data in enumerate(employee_data[:count]):
            # Create user
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'password': make_password('password123'),
                    'is_active': True,
                }
            )
            if created:
                user.tenants.add(school)

            # Create employee
            employee = Employee.objects.create(
                tenant=school,
                employee_number=data['employee_number'],
                joining_date='2020-01-15',
                first_name=data['first_name'],
                last_name=data['last_name'],
                gender=i % 2 == 0,  # Alternate male/female
                job_title=data['job_title'],
                qualification=data['qualification'],
                date_of_birth=data['dob'],
                nationality_id=country_id,
                home_country_id=country_id,
                home_city='Lusaka',
                home_state='Lusaka Province',
                email=data['email'],
                mobile_phone=f'+26097123456{9+i}',
                user=user,
                status=True,
                employment_status='active',
                national_id=f'{123456+i}/78/1',
                emergency_contact_name='Emergency Contact',
                emergency_contact_phone='+260971111111',
                emergency_contact_relation='Relative',
                is_teaching_staff=data['is_teaching_staff'],
            )

            self.stdout.write(f"  ✓ Created employee: {employee.full_name} ({employee.employee_number})")
