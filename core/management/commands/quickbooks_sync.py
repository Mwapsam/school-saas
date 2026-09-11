"""
Django management command for QuickBooks customer synchronization

Usage:
    python manage.py quickbooks_sync --tenant-id=1 --test-student=123
    python manage.py quickbooks_sync --tenant-id=1 --sync-all --limit=10
    python manage.py quickbooks_sync --tenant-id=1 --status
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Student, School
from core.services.quickbooks_service import QuickBooksService
from core.signals import (
    sync_student_to_quickbooks_customer,
    sync_all_students_to_quickbooks,
    is_quickbooks_enabled,
    create_customer_from_student
)


class Command(BaseCommand):
    help = 'Manage QuickBooks customer synchronization for students'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Tenant (School) ID to sync',
            required=True
        )
        
        parser.add_argument(
            '--test-student',
            type=str,
            help='Test sync for a specific student ID (UUID)'
        )
        
        parser.add_argument(
            '--sync-all',
            action='store_true',
            help='Sync all students in the tenant'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of students to sync (use with --sync-all)'
        )
        
        parser.add_argument(
            '--status',
            action='store_true',
            help='Check QuickBooks connection status for the tenant'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually doing it'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if QuickBooks is not enabled'
        )

    def handle(self, *args, **options):
        tenant_id = options['tenant_id']
        
        try:
            tenant = School.objects.get(id=tenant_id)
            self.stdout.write(f"Working with tenant: {tenant.name} (ID: {tenant.id})")
        except School.DoesNotExist:
            raise CommandError(f'Tenant with ID {tenant_id} does not exist')

        # Check status
        if options['status']:
            self.check_status(tenant)
            return

        # Test single student
        if options['test_student']:
            self.test_single_student(options['test_student'], options['dry_run'], options['force'])
            return

        # Sync all students
        if options['sync_all']:
            self.sync_all_students(tenant, options['limit'], options['dry_run'], options['force'])
            return

        # If no specific action, show help
        self.stdout.write(self.style.WARNING('No action specified. Use --help for available options.'))

    def check_status(self, tenant):
        """Check QuickBooks connection status"""
        self.stdout.write(f"\n{self.style.HTTP_INFO}QuickBooks Status for {tenant.name}:")
        self.stdout.write("=" * 50)
        
        # Check if QuickBooks is enabled
        enabled = is_quickbooks_enabled(tenant)
        status_color = self.style.SUCCESS if enabled else self.style.ERROR
        self.stdout.write(f"QuickBooks Enabled: {status_color(enabled)}")
        
        if not enabled:
            self.stdout.write(self.style.WARNING("QuickBooks integration is not enabled or not properly configured."))
            return
        
        # Get detailed status
        try:
            qb_service = QuickBooksService(tenant)
            connection_status = qb_service.get_connection_status()
            
            self.stdout.write(f"Connection Status: {self.style.SUCCESS(connection_status['status'])}")
            self.stdout.write(f"Message: {connection_status['message']}")
            
            if connection_status.get('company_name'):
                self.stdout.write(f"Company: {connection_status['company_name']}")
            if connection_status.get('environment'):
                self.stdout.write(f"Environment: {connection_status['environment']}")
            if connection_status.get('last_sync'):
                self.stdout.write(f"Last Sync: {connection_status['last_sync']}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error checking QuickBooks status: {str(e)}"))

    def test_single_student(self, student_id, dry_run=False, force=False):
        """Test sync for a single student"""
        self.stdout.write(f"\n{self.style.HTTP_INFO}Testing student sync for ID: {student_id}")
        self.stdout.write("=" * 50)
        
        try:
            student = Student.objects.get(id=student_id)
            self.stdout.write(f"Student: {student.first_name} {student.last_name} ({student.admission_no})")
            self.stdout.write(f"Email: {student.email or 'No email'}")
            self.stdout.write(f"Phone: {student.phone1 or 'No phone'}")
            self.stdout.write(f"Active: {student.is_active}")
            
            if dry_run:
                self.stdout.write(f"\n{self.style.WARNING}DRY RUN - Showing what would be created:")
                customer = create_customer_from_student(student)
                self.stdout.write(f"QuickBooks Customer Name: {customer.DisplayName}")
                self.stdout.write(f"Email: {customer.PrimaryEmailAddr.Address if customer.PrimaryEmailAddr else 'None'}")
                self.stdout.write(f"Phone: {customer.PrimaryPhone.FreeFormNumber if customer.PrimaryPhone else 'None'}")
                if customer.BillAddr:
                    self.stdout.write(f"Address: {customer.BillAddr.Line1}, {customer.BillAddr.City}")
                return
            
            # Perform actual sync
            result = sync_student_to_quickbooks_customer(student_id, force=force)
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f"✓ {result['message']}"))
                self.stdout.write(f"QuickBooks Customer ID: {result.get('quickbooks_customer_id')}")
                self.stdout.write(f"Customer Name: {result.get('customer_name')}")
            else:
                self.stdout.write(self.style.ERROR(f"✗ {result['message']}"))
                
        except Student.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Student with ID {student_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error testing student sync: {str(e)}"))

    def sync_all_students(self, tenant, limit=None, dry_run=False, force=False):
        """Sync all students in tenant"""
        self.stdout.write(f"\n{self.style.HTTP_INFO}Syncing all students for {tenant.name}")
        if limit:
            self.stdout.write(f"Limit: {limit} students")
        self.stdout.write("=" * 50)
        
        # Get students count
        students_query = Student.objects.filter(tenant=tenant, is_active=True, is_deleted=False)
        total_count = students_query.count()
        
        if limit:
            students_query = students_query[:limit]
            actual_count = min(total_count, limit)
        else:
            actual_count = total_count
        
        self.stdout.write(f"Found {total_count} active students")
        if limit and limit < total_count:
            self.stdout.write(f"Will sync {actual_count} students (limited)")
        
        if actual_count == 0:
            self.stdout.write(self.style.WARNING("No students to sync"))
            return
        
        if dry_run:
            self.stdout.write(f"\n{self.style.WARNING}DRY RUN - Would sync {actual_count} students")
            for student in students_query:
                customer = create_customer_from_student(student)
                self.stdout.write(f"  • {student.admission_no}: {customer.DisplayName}")
            return
        
        # Confirm before proceeding
        if actual_count > 10:
            response = input(f"Are you sure you want to sync {actual_count} students? (y/N): ")
            if response.lower() != 'y':
                self.stdout.write("Cancelled by user")
                return
        
        # Perform sync
        result = sync_all_students_to_quickbooks(tenant, limit)
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✓ {result['message']}"))
            self.stdout.write(f"Total Students: {result['total_students']}")
            self.stdout.write(f"Successful: {result['successful_syncs']}")
            self.stdout.write(f"Failed: {result['failed_syncs']}")
            
            if result['errors']:
                self.stdout.write(f"\n{self.style.WARNING}Sample Errors:")
                for error in result['errors'][:5]:
                    self.stdout.write(f"  • {error}")
        else:
            self.stdout.write(self.style.ERROR(f"✗ {result['message']}"))