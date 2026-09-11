from django.core.management.base import BaseCommand
from django.apps import apps

from core.utils.model_field_validator import ModelFieldValidator, model_field_validator
from core.models import Student, Guardian


class Command(BaseCommand):
    help = 'Validate model fields and check for potential field mismatch issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            help='Specific model to validate (e.g., Student, Guardian)'
        )
        
        parser.add_argument(
            '--app',
            type=str,
            default='core',
            help='Django app to check models in (default: core)'
        )
        
        parser.add_argument(
            '--check-usage',
            action='store_true',
            help='Check for potential field usage issues in code'
        )
        
        parser.add_argument(
            '--generate-report',
            action='store_true',
            help='Generate detailed field reports for models'
        )
        
        parser.add_argument(
            '--test-student-data',
            action='store_true',
            help='Test student field validation with actual data'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('🔍 Starting Model Field Validation'))
        self.stdout.write('=' * 60)
        
        if options['test_student_data']:
            self.test_student_data_validation()
            return
            
        if options['generate_report']:
            self.generate_field_reports(options['app'], options['model'])
            return
        
        if options['check_usage']:
            self.check_field_usage_issues()
            return
            
        # Default: validate specific model or all models in app
        self.validate_models(options['app'], options['model'])

    def validate_models(self, app_name: str, model_name: str = None):
        """Validate models for field consistency"""
        
        try:
            app_config = apps.get_app_config(app_name)
        except LookupError:
            self.stdout.write(self.style.ERROR(f'App "{app_name}" not found'))
            return
        
        models_to_check = []
        
        if model_name:
            try:
                model_class = app_config.get_model(model_name)
                models_to_check = [model_class]
            except LookupError:
                self.stdout.write(self.style.ERROR(f'Model "{model_name}" not found in app "{app_name}"'))
                return
        else:
            models_to_check = app_config.get_models()
        
        self.stdout.write(f'Validating {len(models_to_check)} model(s) in app "{app_name}"')
        
        validator = ModelFieldValidator()
        
        for model_class in models_to_check:
            self.stdout.write(f'\n📋 Validating {model_class.__name__}...')
            
            fields = validator.get_model_fields(model_class)
            
            self.stdout.write(f'  Total fields: {len(fields)}')
            
            # Check for common field naming issues
            field_issues = self._check_common_field_issues(fields)
            
            if field_issues:
                self.stdout.write(self.style.WARNING('  ⚠️ Potential Issues Found:'))
                for issue in field_issues:
                    self.stdout.write(f'    • {issue}')
            else:
                self.stdout.write(self.style.SUCCESS('  ✅ No obvious field issues detected'))
            
            # Show critical fields for important models
            if model_class.__name__ in ['Student', 'Guardian']:
                self._show_critical_fields(model_class, fields)

    def _check_common_field_issues(self, fields: dict) -> list:
        """Check for common field naming issues"""
        issues = []
        field_names = set(fields.keys())
        
        # Check for potentially confusing field names
        confusing_pairs = [
            ('phone', 'mobile', 'phone1', 'phone2', 'mobile_phone'),
            ('address', 'address_line1', 'street_address'),
            ('zip_code', 'postal_code', 'pin_code'),
            ('active', 'is_active'),
            ('deleted', 'is_deleted'),
        ]
        
        for field_group in confusing_pairs:
            found_fields = [f for f in field_group if f in field_names]
            if len(found_fields) > 1:
                issues.append(f"Multiple similar fields found: {', '.join(found_fields)}")
        
        # Check for fields that might not exist but are commonly expected
        expected_fields = {
            'Student': ['first_name', 'last_name', 'email', 'phone1', 'is_active'],
            'Guardian': ['first_name', 'last_name', 'email', 'mobile_phone'],
        }
        
        model_name = next(iter(fields.values())).__class__.__module__.split('.')[-1]
        if model_name in expected_fields:
            for expected_field in expected_fields[model_name]:
                if expected_field not in field_names:
                    issues.append(f"Expected field '{expected_field}' not found")
        
        return issues

    def _show_critical_fields(self, model_class, fields: dict):
        """Show critical fields for important models"""
        critical_field_groups = {
            'Student': {
                'Identity': ['first_name', 'last_name', 'middle_name', 'admission_no'],
                'Contact': ['email', 'phone1', 'phone2'],
                'Address': ['address_line1', 'address_line2', 'city', 'state', 'pin_code', 'country'],
                'Status': ['is_active', 'is_deleted'],
            },
            'Guardian': {
                'Identity': ['first_name', 'last_name'],
                'Contact': ['email', 'mobile_phone', 'office_phone'],
                'Address': ['office_address_line1', 'office_address_line2', 'city', 'state', 'country'],
            }
        }
        
        model_name = model_class.__name__
        if model_name in critical_field_groups:
            self.stdout.write(f'  📂 Critical Fields for {model_name}:')
            
            for group_name, field_list in critical_field_groups[model_name].items():
                existing_fields = [f for f in field_list if f in fields]
                missing_fields = [f for f in field_list if f not in fields]
                
                self.stdout.write(f'    {group_name}:')
                
                if existing_fields:
                    self.stdout.write(f'      ✅ Found: {", ".join(existing_fields)}')
                
                if missing_fields:
                    self.stdout.write(self.style.WARNING(f'      ❌ Missing: {", ".join(missing_fields)}'))

    def generate_field_reports(self, app_name: str, model_name: str = None):
        """Generate detailed field reports"""
        self.stdout.write('📊 Generating Field Reports...\n')
        
        try:
            app_config = apps.get_app_config(app_name)
        except LookupError:
            self.stdout.write(self.style.ERROR(f'App "{app_name}" not found'))
            return
        
        models_to_report = []
        
        if model_name:
            try:
                model_class = app_config.get_model(model_name)
                models_to_report = [model_class]
            except LookupError:
                self.stdout.write(self.style.ERROR(f'Model "{model_name}" not found'))
                return
        else:
            models_to_report = [Student, Guardian]  # Focus on key models
        
        validator = ModelFieldValidator()
        
        for model_class in models_to_report:
            report = validator.create_field_mapping_report(model_class)
            self.stdout.write(report)
            self.stdout.write('')  # Add spacing

    def check_field_usage_issues(self):
        """Check for potential field usage issues in code"""
        self.stdout.write('🔍 Checking for Field Usage Issues...\n')
        
        # Common field usage issues to look for
        potential_issues = [
            {
                'description': 'Usage of mobile_number (should be phone1/phone2)',
                'pattern': 'mobile_number',
                'suggestion': 'Use phone1 or phone2 instead'
            },
            {
                'description': 'Usage of postal_code (should be pin_code)',
                'pattern': 'postal_code',
                'suggestion': 'Use pin_code instead for Student model'
            },
            {
                'description': 'Direct field access without validation',
                'pattern': 'student.phone1',
                'suggestion': 'Consider using StudentFieldHelper.get_phone_number()'
            }
        ]
        
        self.stdout.write('Common field usage issues to watch for:')
        for i, issue in enumerate(potential_issues, 1):
            self.stdout.write(f'{i}. {issue["description"]}')
            self.stdout.write(f'   Pattern: {issue["pattern"]}')
            self.stdout.write(f'   Suggestion: {issue["suggestion"]}\n')

    def test_student_data_validation(self):
        """Test student field validation with actual data"""
        from core.utils.model_field_validator import get_student_quickbooks_data, validate_student_fields_for_quickbooks
        
        self.stdout.write('🧪 Testing Student Data Validation...\n')
        
        # Get first few students for testing
        students = Student.objects.all()[:5]
        
        if not students:
            self.stdout.write(self.style.WARNING('No students found for testing'))
            return
        
        for student in students:
            self.stdout.write(f'Testing student: {student.admission_no}')
            
            try:
                # Test basic validation
                is_valid = validate_student_fields_for_quickbooks(student)
                self.stdout.write(f'  Valid for sync: {is_valid}')
                
                # Get detailed data
                student_data = get_student_quickbooks_data(student)
                
                # Show key fields
                key_fields = [
                    'display_name', 'email', 'phone', 'is_active', 'is_ready_for_sync'
                ]
                
                for field in key_fields:
                    value = student_data.get(field, 'N/A')
                    self.stdout.write(f'  {field}: {value}')
                
                # Show validation results
                validation = student_data['validation_results']
                failed_validations = [k for k, v in validation.items() if not v and k.startswith('has_')]
                
                if failed_validations:
                    self.stdout.write(self.style.WARNING(f'  Missing: {", ".join(failed_validations)}'))
                else:
                    self.stdout.write(self.style.SUCCESS('  ✅ All validations passed'))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {str(e)}'))
            
            self.stdout.write('')  # Add spacing