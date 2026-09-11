import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from celery.result import AsyncResult

from core.models import School, Student, QuickBooksCustomerSync
from core.tasks import (
    sync_admitted_students_to_quickbooks,
    sync_all_tenants_students_to_quickbooks,
    sync_single_student_to_quickbooks,
    cleanup_failed_quickbooks_syncs,
    proactive_quickbooks_token_refresh,
    check_quickbooks_token_health
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync admitted students to QuickBooks using Celery tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Tenant ID or domain to sync students for'
        )
        
        parser.add_argument(
            '--student',
            type=str,
            help='Student ID to sync (syncs only this student)'
        )
        
        parser.add_argument(
            '--all-tenants',
            action='store_true',
            help='Sync students for all active tenants'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of students to process (per tenant if applicable)'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sync of already synced students'
        )
        
        parser.add_argument(
            '--async',
            action='store_true',
            dest='run_async',
            help='Run task asynchronously (default: synchronous)'
        )
        
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up old failed sync records'
        )
        
        parser.add_argument(
            '--cleanup-days',
            type=int,
            default=7,
            help='Days old for cleanup (default: 7)'
        )
        
        parser.add_argument(
            '--status',
            type=str,
            help='Check status of a running task by task ID'
        )
        
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show QuickBooks sync statistics'
        )
        
        parser.add_argument(
            '--refresh-tokens',
            action='store_true',
            help='Proactively refresh QuickBooks tokens that will expire soon'
        )
        
        parser.add_argument(
            '--health-check',
            action='store_true',
            help='Check health of all QuickBooks integrations'
        )

    def handle(self, *args, **options):
        try:
            # Check task status
            if options['status']:
                self.check_task_status(options['status'])
                return
            
            # Show statistics
            if options['stats']:
                self.show_sync_stats()
                return
            
            # Refresh tokens
            if options['refresh_tokens']:
                self.refresh_tokens(options['run_async'])
                return
            
            # Health check
            if options['health_check']:
                self.health_check(options['run_async'])
                return
            
            # Cleanup old records
            if options['cleanup']:
                self.run_cleanup(options['cleanup_days'], options['run_async'])
                return
            
            # Single student sync
            if options['student']:
                self.sync_single_student(
                    options['student'], 
                    options['force'],
                    options['run_async']
                )
                return
            
            # All tenants sync
            if options['all_tenants']:
                self.sync_all_tenants(
                    options['limit'],
                    options['force'],
                    options['run_async']
                )
                return
            
            # Single tenant sync
            if options['tenant']:
                self.sync_single_tenant(
                    options['tenant'],
                    options['limit'],
                    options['force'],
                    options['run_async']
                )
                return
            
            # Default: show help
            self.stdout.write(
                self.style.WARNING('Please specify an action: --tenant, --student, --all-tenants, --cleanup, --stats, or --status')
            )
            self.stdout.write('Run with --help for more information')
            
        except CommandError:
            raise
        except Exception as e:
            raise CommandError(f'Command failed: {str(e)}')

    def sync_single_student(self, student_id: str, force: bool, run_async: bool):
        """Sync a single student to QuickBooks"""
        self.stdout.write(f'Starting sync for student ID: {student_id}')
        
        try:
            # Validate student exists
            student = Student.objects.get(id=student_id)
            self.stdout.write(f'Found student: {student.admission_no} - {student.first_name} {student.last_name}')
            
        except Student.DoesNotExist:
            raise CommandError(f'Student with ID {student_id} not found')
        
        # Run the task
        task = sync_single_student_to_quickbooks.delay(student_id, force)
        
        if run_async:
            self.stdout.write(
                self.style.SUCCESS(f'Task started asynchronously. Task ID: {task.id}')
            )
            self.stdout.write(f'Check status with: --status {task.id}')
        else:
            self.stdout.write('Running synchronously...')
            result = task.get()
            self.display_result(result)

    def sync_single_tenant(self, tenant_identifier: str, limit: int, force: bool, run_async: bool):
        """Sync students for a single tenant"""
        # Try to find tenant by ID first, then by domain
        tenant = None
        try:
            tenant = School.objects.get(id=tenant_identifier)
        except (School.DoesNotExist, ValueError):
            try:
                tenant = School.objects.get(schema_name=tenant_identifier)
            except School.DoesNotExist:
                try:
                    tenant = School.objects.get(domains__domain=tenant_identifier)
                except School.DoesNotExist:
                    pass
        
        if not tenant:
            raise CommandError(f'Tenant not found: {tenant_identifier}')
        
        self.stdout.write(f'Starting sync for tenant: {tenant.name} ({tenant.id})')
        
        # Show current stats
        total_students = Student.objects.filter(tenant=tenant, is_active=True, is_deleted=False).count()
        synced_count = QuickBooksCustomerSync.objects.filter(tenant=tenant, sync_status='synced').count()
        
        self.stdout.write(f'Students in tenant: {total_students}')
        self.stdout.write(f'Already synced: {synced_count}')
        self.stdout.write(f'To be processed: {total_students - (0 if force else synced_count)}')
        
        # Run the task
        task = sync_admitted_students_to_quickbooks.delay(str(tenant.id), limit, force)
        
        if run_async:
            self.stdout.write(
                self.style.SUCCESS(f'Task started asynchronously. Task ID: {task.id}')
            )
            self.stdout.write(f'Check status with: --status {task.id}')
        else:
            self.stdout.write('Running synchronously...')
            result = task.get()
            self.display_result(result)

    def sync_all_tenants(self, limit: int, force: bool, run_async: bool):
        """Sync students for all active tenants"""
        tenant_count = School.objects.filter(is_active=True).count()
        
        self.stdout.write(f'Starting sync for all tenants: {tenant_count} active tenants found')
        
        # Run the task
        task = sync_all_tenants_students_to_quickbooks.delay(limit, force)
        
        if run_async:
            self.stdout.write(
                self.style.SUCCESS(f'Task started asynchronously. Task ID: {task.id}')
            )
            self.stdout.write(f'Check status with: --status {task.id}')
        else:
            self.stdout.write('Running synchronously...')
            result = task.get()
            self.display_result(result)

    def run_cleanup(self, days_old: int, run_async: bool):
        """Clean up old failed sync records"""
        self.stdout.write(f'Starting cleanup of sync records older than {days_old} days')
        
        task = cleanup_failed_quickbooks_syncs.delay(days_old)
        
        if run_async:
            self.stdout.write(
                self.style.SUCCESS(f'Cleanup task started asynchronously. Task ID: {task.id}')
            )
            self.stdout.write(f'Check status with: --status {task.id}')
        else:
            self.stdout.write('Running synchronously...')
            result = task.get()
            self.display_result(result)

    def check_task_status(self, task_id: str):
        """Check the status of a running task"""
        try:
            result = AsyncResult(task_id)
            
            self.stdout.write(f'Task ID: {task_id}')
            self.stdout.write(f'Status: {result.status}')
            
            if result.status == 'PENDING':
                self.stdout.write('Task is waiting to be processed')
            elif result.status == 'PROGRESS':
                info = result.info
                self.stdout.write(f'Progress: {info}')
            elif result.status == 'SUCCESS':
                self.stdout.write(self.style.SUCCESS('Task completed successfully'))
                self.display_result(result.result)
            elif result.status == 'FAILURE':
                self.stdout.write(self.style.ERROR('Task failed'))
                self.stdout.write(f'Error: {result.info}')
            else:
                self.stdout.write(f'Unknown status: {result.status}')
                
        except Exception as e:
            raise CommandError(f'Failed to check task status: {str(e)}')

    def show_sync_stats(self):
        """Show QuickBooks sync statistics"""
        self.stdout.write(self.style.HTTP_INFO('QuickBooks Sync Statistics'))
        self.stdout.write('=' * 50)
        
        for tenant in School.objects.filter(is_active=True):
            self.stdout.write(f'\nTenant: {tenant.name}')
            
            total_students = Student.objects.filter(tenant=tenant, is_active=True, is_deleted=False).count()
            synced_students = QuickBooksCustomerSync.objects.filter(tenant=tenant, sync_status='synced').count()
            pending_students = QuickBooksCustomerSync.objects.filter(tenant=tenant, sync_status='pending').count()
            failed_students = QuickBooksCustomerSync.objects.filter(tenant=tenant, sync_status='failed').count()
            
            self.stdout.write(f'  Total Active Students: {total_students}')
            self.stdout.write(f'  Synced to QuickBooks: {synced_students}')
            self.stdout.write(f'  Pending Sync: {pending_students}')
            self.stdout.write(f'  Failed Sync: {failed_students}')
            self.stdout.write(f'  Not Yet Synced: {total_students - synced_students - pending_students - failed_students}')
        
        # Overall statistics
        self.stdout.write('\n' + '=' * 50)
        total_all = Student.objects.filter(is_active=True, is_deleted=False).count()
        synced_all = QuickBooksCustomerSync.objects.filter(sync_status='synced').count()
        
        self.stdout.write(f'Overall: {synced_all}/{total_all} students synced to QuickBooks')

    def display_result(self, result: dict):
        """Display task result in a formatted way"""
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS('✓ Task completed successfully'))
        else:
            self.stdout.write(self.style.ERROR('✗ Task failed'))
        
        # Display key metrics
        for key, value in result.items():
            if key in ['success', 'errors', 'tenant_results']:
                continue
                
            if isinstance(value, (int, float)):
                self.stdout.write(f'{key.replace("_", " ").title()}: {value}')
            elif isinstance(value, str) and len(value) < 200:
                self.stdout.write(f'{key.replace("_", " ").title()}: {value}')
        
        # Display errors if any
        if 'errors' in result and result['errors']:
            self.stdout.write(self.style.WARNING('\nErrors encountered:'))
            for error in result['errors'][:5]:  # Show first 5 errors
                if isinstance(error, dict):
                    self.stdout.write(f'  • {error.get("student_id", "Unknown")}: {error.get("error", "Unknown error")}')
                else:
                    self.stdout.write(f'  • {error}')
            
            if len(result['errors']) > 5:
                self.stdout.write(f'  ... and {len(result["errors"]) - 5} more errors')
        
        # Display tenant results summary for multi-tenant operations
        if 'tenant_results' in result and result['tenant_results']:
            successful_tenants = sum(1 for r in result['tenant_results'] if r.get('success'))
            self.stdout.write(f'\nTenant Results: {successful_tenants}/{len(result["tenant_results"])} tenants successful')

    def refresh_tokens(self, run_async: bool):
        """Proactively refresh QuickBooks tokens"""
        self.stdout.write('Starting proactive QuickBooks token refresh...')
        
        task = proactive_quickbooks_token_refresh.delay()
        
        if run_async:
            self.stdout.write(
                self.style.SUCCESS(f'Token refresh task started asynchronously. Task ID: {task.id}')
            )
            self.stdout.write(f'Check status with: --status {task.id}')
        else:
            self.stdout.write('Running synchronously...')
            result = task.get()
            self.display_result(result)
    
    def health_check(self, run_async: bool):
        """Check QuickBooks integration health"""
        self.stdout.write('Starting QuickBooks integration health check...')
        
        task = check_quickbooks_token_health.delay()
        
        if run_async:
            self.stdout.write(
                self.style.SUCCESS(f'Health check task started asynchronously. Task ID: {task.id}')
            )
            self.stdout.write(f'Check status with: --status {task.id}')
        else:
            self.stdout.write('Running synchronously...')
            result = task.get()
            self.display_health_result(result)
    
    def display_health_result(self, result: dict):
        """Display health check result in a formatted way"""
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS('✓ Health check completed'))
            
            # Display summary
            if 'summary' in result:
                self.stdout.write(f"\n{result['summary']}")
            
            # Display statistics
            stats = [
                ('Total Integrations', result.get('total_integrations', 0)),
                ('Healthy', result.get('healthy_integrations', 0)),
                ('Expiring Soon (< 1hr)', result.get('expiring_soon', 0)),
                ('Expired Tokens', result.get('expired_tokens', 0)),
                ('Missing Refresh Tokens', result.get('missing_refresh_tokens', 0)),
                ('Connection Issues', result.get('connection_issues', 0))
            ]
            
            self.stdout.write('\n' + '=' * 50)
            for label, value in stats:
                color = self.style.SUCCESS if value == 0 or label in ['Total Integrations', 'Healthy'] else self.style.WARNING
                self.stdout.write(color(f'{label}: {value}'))
            
            # Display details for problematic integrations
            if 'details' in result:
                problem_integrations = [
                    detail for detail in result['details'] 
                    if detail.get('status') not in ['healthy']
                ]
                
                if problem_integrations:
                    self.stdout.write('\n' + self.style.WARNING('Integrations needing attention:'))
                    for detail in problem_integrations[:10]:  # Show first 10
                        status_color = self.style.ERROR if detail.get('status') in ['expired', 'connection_failed'] else self.style.WARNING
                        self.stdout.write(status_color(
                            f"  • {detail.get('tenant_name', 'Unknown')}: {detail.get('status', 'unknown')}"
                        ))
                        if detail.get('time_until_expiry_minutes') is not None:
                            self.stdout.write(f"    Time until expiry: {detail['time_until_expiry_minutes']} minutes")
                        if detail.get('connection_error'):
                            self.stdout.write(f"    Error: {detail['connection_error']}")
        else:
            self.stdout.write(self.style.ERROR('✗ Health check failed'))
            if 'error' in result:
                self.stdout.write(f'Error: {result["error"]}'))