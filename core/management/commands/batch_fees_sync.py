"""
Django management command for batch enrollment to fee synchronization

Usage:
    python manage.py batch_fees_sync --tenant-id=1 --test-enrollment=123
    python manage.py batch_fees_sync --tenant-id=1 --sync-all --limit=10
    python manage.py batch_fees_sync --tenant-id=1 --student-batch --student-id=123 --batch-id=456
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Student, School, BatchStudent, BatchFeeCategory, FinanceFee
from core.signals import (
    create_batch_fees_for_student,
    sync_all_batch_fees_for_tenant
)


class Command(BaseCommand):
    help = 'Manage batch enrollment to fee collection synchronization'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Tenant (School) ID to sync',
            required=True
        )
        
        parser.add_argument(
            '--test-enrollment',
            type=str,
            help='Test fee creation for a specific BatchStudent enrollment ID'
        )
        
        parser.add_argument(
            '--student-batch',
            action='store_true',
            help='Create fees for specific student-batch combination'
        )
        
        parser.add_argument(
            '--student-id',
            type=str,
            help='Student ID for specific enrollment (use with --student-batch)'
        )
        
        parser.add_argument(
            '--batch-id',
            type=str,
            help='Batch ID for specific enrollment (use with --student-batch)'
        )
        
        parser.add_argument(
            '--sync-all',
            action='store_true',
            help='Sync all enrollments in the tenant'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of enrollments to sync (use with --sync-all)'
        )
        
        parser.add_argument(
            '--status',
            action='store_true',
            help='Check batch fee configuration status for the tenant'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually doing it'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force create fees even if they already exist'
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

        # Test specific enrollment
        if options['test_enrollment']:
            self.test_enrollment_sync(options['test_enrollment'], options['dry_run'], options['force'])
            return

        # Test specific student-batch combination
        if options['student_batch']:
            if not options['student_id'] or not options['batch_id']:
                raise CommandError('--student-id and --batch-id are required when using --student-batch')
            self.test_student_batch_sync(
                options['student_id'], 
                options['batch_id'], 
                options['dry_run'], 
                options['force']
            )
            return

        # Sync all enrollments
        if options['sync_all']:
            self.sync_all_enrollments(tenant, options['limit'], options['dry_run'], options['force'])
            return

        # If no specific action, show help
        self.stdout.write(self.style.WARNING('No action specified. Use --help for available options.'))

    def check_status(self, tenant):
        """Check batch fee configuration status"""
        self.stdout.write(f"\n{self.style.HTTP_INFO}Batch Fee Configuration Status for {tenant.name}:")
        self.stdout.write("=" * 60)
        
        # Check batches
        from core.models import Batch
        batches = Batch.objects.filter(tenant=tenant, is_active=True)
        self.stdout.write(f"Active Batches: {batches.count()}")
        
        # Check batch fee categories
        batch_fee_categories = BatchFeeCategory.objects.filter(tenant=tenant)
        self.stdout.write(f"Batch Fee Categories: {batch_fee_categories.count()}")
        
        # Check enrollments
        enrollments = BatchStudent.objects.filter(tenant=tenant, is_active=True)
        self.stdout.write(f"Active Enrollments: {enrollments.count()}")
        
        # Check existing fees
        existing_fees = FinanceFee.objects.filter(tenant=tenant)
        self.stdout.write(f"Existing Fee Records: {existing_fees.count()}")
        
        # Show batch details
        if batches.exists():
            self.stdout.write(f"\n{self.style.HTTP_INFO}Batch Details:")
            for batch in batches:
                fee_categories = BatchFeeCategory.objects.filter(batch=batch)
                students = BatchStudent.objects.filter(batch=batch, is_active=True).count()
                self.stdout.write(f"  • {batch.name}: {students} students, {fee_categories.count()} fee categories")
                
                for fee_cat in fee_categories:
                    self.stdout.write(f"    - {fee_cat.fee_category.name}: ${fee_cat.amount}")

    def test_enrollment_sync(self, enrollment_id, dry_run=False, force=False):
        """Test sync for a specific BatchStudent enrollment"""
        self.stdout.write(f"\n{self.style.HTTP_INFO}Testing enrollment sync for ID: {enrollment_id}")
        self.stdout.write("=" * 50)
        
        try:
            enrollment = BatchStudent.objects.get(id=enrollment_id)
            student = enrollment.student
            batch = enrollment.batch
            
            self.stdout.write(f"Student: {student.first_name} {student.last_name} ({student.admission_no})")
            self.stdout.write(f"Batch: {batch.name}")
            self.stdout.write(f"Enrollment Active: {enrollment.is_active}")
            
            # Check batch fee categories
            batch_fee_categories = BatchFeeCategory.objects.filter(batch=batch)
            self.stdout.write(f"Batch Fee Categories: {batch_fee_categories.count()}")
            
            for fee_cat in batch_fee_categories:
                self.stdout.write(f"  • {fee_cat.fee_category.name}: ${fee_cat.amount}")
            
            if dry_run:
                self.stdout.write(f"\n{self.style.WARNING}DRY RUN - Would create {batch_fee_categories.count()} fee records")
                return
            
            # Perform actual sync
            result = create_batch_fees_for_student(
                str(student.id), 
                str(batch.id), 
                force=force
            )
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f"✓ {result['message']}"))
                self.stdout.write(f"Fees Created: {result.get('fees_created', 0)}")
                self.stdout.write(f"Fees Skipped: {result.get('fees_skipped', 0)}")
                
                for fee in result.get('fees', []):
                    action_color = self.style.SUCCESS if fee['action'] == 'created' else self.style.WARNING
                    self.stdout.write(f"  • {action_color(fee['action'].title())}: {fee['category']} - ${fee['amount']}")
            else:
                self.stdout.write(self.style.ERROR(f"✗ {result['message']}"))
                
        except BatchStudent.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Enrollment with ID {enrollment_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error testing enrollment sync: {str(e)}"))

    def test_student_batch_sync(self, student_id, batch_id, dry_run=False, force=False):
        """Test sync for specific student-batch combination"""
        self.stdout.write(f"\n{self.style.HTTP_INFO}Testing student-batch fee sync")
        self.stdout.write(f"Student ID: {student_id}, Batch ID: {batch_id}")
        self.stdout.write("=" * 50)
        
        try:
            student = Student.objects.get(id=student_id)
            from core.models import Batch
            batch = Batch.objects.get(id=batch_id)
            
            self.stdout.write(f"Student: {student.first_name} {student.last_name} ({student.admission_no})")
            self.stdout.write(f"Batch: {batch.name}")
            
            # Check if enrollment exists
            enrollment = BatchStudent.objects.filter(student=student, batch=batch).first()
            if enrollment:
                self.stdout.write(f"Enrollment exists: Active={enrollment.is_active}")
            else:
                self.stdout.write(self.style.WARNING("No enrollment record found"))
            
            if dry_run:
                batch_fee_categories = BatchFeeCategory.objects.filter(batch=batch)
                self.stdout.write(f"\n{self.style.WARNING}DRY RUN - Would process {batch_fee_categories.count()} fee categories")
                for fee_cat in batch_fee_categories:
                    self.stdout.write(f"  • {fee_cat.fee_category.name}: ${fee_cat.amount}")
                return
            
            # Perform sync
            result = create_batch_fees_for_student(student_id, batch_id, force=force)
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f"✓ {result['message']}"))
                for fee in result.get('fees', []):
                    action_color = self.style.SUCCESS if fee['action'] == 'created' else self.style.WARNING
                    self.stdout.write(f"  • {action_color(fee['action'].title())}: {fee['category']} - ${fee['amount']}")
            else:
                self.stdout.write(self.style.ERROR(f"✗ {result['message']}"))
                
        except Student.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Student with ID {student_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error testing student-batch sync: {str(e)}"))

    def sync_all_enrollments(self, tenant, limit=None, dry_run=False, force=False):
        """Sync all enrollments in tenant"""
        self.stdout.write(f"\n{self.style.HTTP_INFO}Syncing all enrollments for {tenant.name}")
        if limit:
            self.stdout.write(f"Limit: {limit} enrollments")
        self.stdout.write("=" * 50)
        
        # Get enrollment count
        enrollments_query = BatchStudent.objects.filter(
            tenant=tenant, 
            is_active=True,
            student__is_active=True,
            student__is_deleted=False
        )
        total_count = enrollments_query.count()
        
        if limit:
            enrollments_query = enrollments_query[:limit]
            actual_count = min(total_count, limit)
        else:
            actual_count = total_count
        
        self.stdout.write(f"Found {total_count} active enrollments")
        if limit and limit < total_count:
            self.stdout.write(f"Will process {actual_count} enrollments (limited)")
        
        if actual_count == 0:
            self.stdout.write(self.style.WARNING("No enrollments to sync"))
            return
        
        if dry_run:
            self.stdout.write(f"\n{self.style.WARNING}DRY RUN - Would sync {actual_count} enrollments")
            for enrollment in enrollments_query:
                batch_fees = BatchFeeCategory.objects.filter(batch=enrollment.batch).count()
                self.stdout.write(f"  • {enrollment.student.admission_no} in {enrollment.batch.name}: {batch_fees} potential fees")
            return
        
        # Confirm before proceeding
        if actual_count > 10:
            response = input(f"Are you sure you want to sync {actual_count} enrollments? (y/N): ")
            if response.lower() != 'y':
                self.stdout.write("Cancelled by user")
                return
        
        # Perform sync
        result = sync_all_batch_fees_for_tenant(tenant, limit)
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✓ {result['message']}"))
            self.stdout.write(f"Total Enrollments: {result['total_enrollments']}")
            self.stdout.write(f"Enrollments Processed: {result['enrollments_processed']}")
            self.stdout.write(f"Fees Created: {result['fees_created']}")
            
            if result.get('errors'):
                self.stdout.write(f"\n{self.style.WARNING}Sample Errors:")
                for error in result['errors'][:5]:
                    self.stdout.write(f"  • {error}")
        else:
            self.stdout.write(self.style.ERROR(f"✗ {result['message']}"))