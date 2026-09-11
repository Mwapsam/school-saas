"""
Utility functions for managing QuickBooks synchronization tasks.

This module provides convenient functions to trigger and monitor
QuickBooks sync tasks from views, signals, or other parts of the application.
"""

import logging
from typing import Dict, Any, Optional, List
from celery.result import AsyncResult
from django.utils import timezone

from core.models import School, Student, QuickBooksCustomerSync
from core.tasks import (
    sync_admitted_students_to_quickbooks,
    sync_all_tenants_students_to_quickbooks,
    sync_single_student_to_quickbooks,
    cleanup_failed_quickbooks_syncs
)
from core.services.quickbooks_service import QuickBooksService

logger = logging.getLogger(__name__)


class QuickBooksSyncManager:
    """
    Manager class for QuickBooks synchronization operations.
    
    Provides high-level methods to trigger and monitor sync tasks.
    """
    
    @staticmethod
    def sync_tenant_students(tenant_id: str, limit: Optional[int] = None, 
                           force_resync: bool = False, 
                           run_async: bool = True) -> Dict[str, Any]:
        """
        Sync all students for a specific tenant to QuickBooks.
        
        Args:
            tenant_id: UUID of the tenant
            limit: Optional limit on students to process
            force_resync: Re-sync already synced students
            run_async: Run as Celery task (True) or synchronously (False)
            
        Returns:
            Dict with task info or results
        """
        try:
            # Validate tenant exists
            tenant = School.objects.get(id=tenant_id)
            
            # Check QuickBooks connection
            qb_service = QuickBooksService(tenant)
            connection_status = qb_service.get_connection_status()
            
            if not connection_status['connected']:
                return {
                    'success': False,
                    'error': f'QuickBooks not connected: {connection_status["message"]}',
                    'status': connection_status['status']
                }
            
            # Get sync statistics before starting
            total_students = Student.objects.filter(
                tenant=tenant, is_active=True, is_deleted=False
            ).count()
            
            already_synced = QuickBooksCustomerSync.objects.filter(
                tenant=tenant, sync_status='synced'
            ).count()
            
            logger.info(f"Starting QuickBooks sync for tenant {tenant.name}: "
                       f"{total_students} total students, {already_synced} already synced")
            
            # Start the sync task
            task = sync_admitted_students_to_quickbooks.delay(
                str(tenant_id), limit, force_resync
            )
            
            if run_async:
                return {
                    'success': True,
                    'task_id': task.id,
                    'tenant_id': str(tenant_id),
                    'tenant_name': tenant.name,
                    'total_students': total_students,
                    'already_synced': already_synced,
                    'students_to_process': total_students - (0 if force_resync else already_synced),
                    'message': f'Sync task started for {tenant.name}',
                    'async': True
                }
            else:
                # Wait for completion
                result = task.get()
                return result
                
        except School.DoesNotExist:
            return {
                'success': False,
                'error': f'Tenant with ID {tenant_id} not found'
            }
        except Exception as e:
            logger.error(f"Error starting tenant sync for {tenant_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def sync_single_student(student_id: str, force_resync: bool = False, 
                          run_async: bool = True) -> Dict[str, Any]:
        """
        Sync a single student to QuickBooks.
        
        Args:
            student_id: UUID of the student
            force_resync: Re-sync even if already synced
            run_async: Run as Celery task (True) or synchronously (False)
            
        Returns:
            Dict with task info or results
        """
        try:
            # Validate student exists
            student = Student.objects.select_related('tenant').get(id=student_id)
            
            # Check QuickBooks connection
            qb_service = QuickBooksService(student.tenant)
            connection_status = qb_service.get_connection_status()
            
            if not connection_status['connected']:
                return {
                    'success': False,
                    'error': f'QuickBooks not connected for {student.tenant.name}: {connection_status["message"]}',
                    'status': connection_status['status']
                }
            
            logger.info(f"Starting QuickBooks sync for student {student.admission_no}")
            
            # Start the sync task
            task = sync_single_student_to_quickbooks.delay(str(student_id), force_resync)
            
            if run_async:
                return {
                    'success': True,
                    'task_id': task.id,
                    'student_id': str(student_id),
                    'student_name': f"{student.first_name} {student.last_name}",
                    'student_admission_no': student.admission_no,
                    'message': f'Sync task started for student {student.admission_no}',
                    'async': True
                }
            else:
                # Wait for completion
                result = task.get()
                return result
                
        except Student.DoesNotExist:
            return {
                'success': False,
                'error': f'Student with ID {student_id} not found'
            }
        except Exception as e:
            logger.error(f"Error starting student sync for {student_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def sync_all_tenants(limit_per_tenant: Optional[int] = None,
                        force_resync: bool = False,
                        run_async: bool = True) -> Dict[str, Any]:
        """
        Sync students for all active tenants.
        
        Args:
            limit_per_tenant: Optional limit per tenant
            force_resync: Re-sync already synced students
            run_async: Run as Celery task (True) or synchronously (False)
            
        Returns:
            Dict with task info or results
        """
        try:
            total_tenants = School.objects.filter(is_active=True).count()
            
            if total_tenants == 0:
                return {
                    'success': True,
                    'message': 'No active tenants found',
                    'total_tenants': 0
                }
            
            logger.info(f"Starting QuickBooks sync for all tenants: {total_tenants} tenants")
            
            # Start the sync task
            task = sync_all_tenants_students_to_quickbooks.delay(
                limit_per_tenant, force_resync
            )
            
            if run_async:
                return {
                    'success': True,
                    'task_id': task.id,
                    'total_tenants': total_tenants,
                    'message': f'Multi-tenant sync task started for {total_tenants} tenants',
                    'async': True
                }
            else:
                # Wait for completion
                result = task.get()
                return result
                
        except Exception as e:
            logger.error(f"Error starting multi-tenant sync: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_task_status(task_id: str) -> Dict[str, Any]:
        """
        Get the status of a running QuickBooks sync task.
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Dict with task status information
        """
        try:
            result = AsyncResult(task_id)
            
            response = {
                'task_id': task_id,
                'status': result.status,
                'ready': result.ready(),
                'successful': result.successful() if result.ready() else None
            }
            
            if result.status == 'PENDING':
                response['message'] = 'Task is waiting to be processed'
                
            elif result.status == 'PROGRESS':
                response['progress'] = result.info
                response['message'] = 'Task is running'
                
            elif result.status == 'SUCCESS':
                response['result'] = result.result
                response['message'] = 'Task completed successfully'
                
            elif result.status == 'FAILURE':
                response['error'] = str(result.info)
                response['message'] = 'Task failed'
                
            elif result.status == 'RETRY':
                response['message'] = 'Task is being retried'
                
            elif result.status == 'REVOKED':
                response['message'] = 'Task was cancelled'
                
            else:
                response['message'] = f'Unknown status: {result.status}'
            
            return response
            
        except Exception as e:
            return {
                'task_id': task_id,
                'status': 'ERROR',
                'error': str(e),
                'message': 'Failed to get task status'
            }
    
    @staticmethod
    def get_sync_statistics(tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get QuickBooks sync statistics for a tenant or all tenants.
        
        Args:
            tenant_id: Optional tenant ID. If None, returns stats for all tenants.
            
        Returns:
            Dict with sync statistics
        """
        try:
            stats = {
                'generated_at': timezone.now().isoformat(),
                'tenants': []
            }
            
            # Filter tenants
            tenants_query = School.objects.filter(is_active=True)
            if tenant_id:
                tenants_query = tenants_query.filter(id=tenant_id)
            
            total_students_all = 0
            total_synced_all = 0
            total_failed_all = 0
            total_pending_all = 0
            
            for tenant in tenants_query:
                # Get counts
                total_students = Student.objects.filter(
                    tenant=tenant, is_active=True, is_deleted=False
                ).count()
                
                synced_students = QuickBooksCustomerSync.objects.filter(
                    tenant=tenant, sync_status='synced'
                ).count()
                
                pending_students = QuickBooksCustomerSync.objects.filter(
                    tenant=tenant, sync_status='pending'
                ).count()
                
                failed_students = QuickBooksCustomerSync.objects.filter(
                    tenant=tenant, sync_status='failed'
                ).count()
                
                not_synced = total_students - synced_students - pending_students - failed_students
                
                # Check QuickBooks connection status
                try:
                    qb_service = QuickBooksService(tenant)
                    connection_status = qb_service.get_connection_status()
                    quickbooks_connected = connection_status['connected']
                    quickbooks_status = connection_status['status']
                except Exception:
                    quickbooks_connected = False
                    quickbooks_status = 'error'
                
                tenant_stats = {
                    'tenant_id': str(tenant.id),
                    'tenant_name': tenant.name,
                    'quickbooks_connected': quickbooks_connected,
                    'quickbooks_status': quickbooks_status,
                    'total_active_students': total_students,
                    'synced_to_quickbooks': synced_students,
                    'sync_pending': pending_students,
                    'sync_failed': failed_students,
                    'not_yet_synced': not_synced,
                    'sync_percentage': round((synced_students / total_students * 100) if total_students > 0 else 0, 1)
                }
                
                stats['tenants'].append(tenant_stats)
                
                # Add to totals
                total_students_all += total_students
                total_synced_all += synced_students
                total_failed_all += failed_students
                total_pending_all += pending_students
            
            # Overall statistics
            stats['summary'] = {
                'total_tenants': len(stats['tenants']),
                'total_active_students': total_students_all,
                'total_synced_to_quickbooks': total_synced_all,
                'total_sync_pending': total_pending_all,
                'total_sync_failed': total_failed_all,
                'total_not_yet_synced': total_students_all - total_synced_all - total_pending_all - total_failed_all,
                'overall_sync_percentage': round((total_synced_all / total_students_all * 100) if total_students_all > 0 else 0, 1)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting sync statistics: {str(e)}")
            return {
                'error': str(e),
                'generated_at': timezone.now().isoformat()
            }
    
    @staticmethod
    def cleanup_old_records(days_old: int = 7, run_async: bool = True) -> Dict[str, Any]:
        """
        Clean up old failed sync records.
        
        Args:
            days_old: Number of days old for records to be cleaned
            run_async: Run as Celery task (True) or synchronously (False)
            
        Returns:
            Dict with cleanup info or results
        """
        try:
            logger.info(f"Starting cleanup of QuickBooks sync records older than {days_old} days")
            
            task = cleanup_failed_quickbooks_syncs.delay(days_old)
            
            if run_async:
                return {
                    'success': True,
                    'task_id': task.id,
                    'days_old': days_old,
                    'message': f'Cleanup task started for records older than {days_old} days',
                    'async': True
                }
            else:
                # Wait for completion
                result = task.get()
                return result
                
        except Exception as e:
            logger.error(f"Error starting cleanup task: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Convenience functions for common operations
def quick_sync_tenant(tenant_id: str, **kwargs) -> Dict[str, Any]:
    """Quick function to sync a tenant's students."""
    return QuickBooksSyncManager.sync_tenant_students(tenant_id, **kwargs)


def quick_sync_student(student_id: str, **kwargs) -> Dict[str, Any]:
    """Quick function to sync a single student."""
    return QuickBooksSyncManager.sync_single_student(student_id, **kwargs)


def quick_sync_all(**kwargs) -> Dict[str, Any]:
    """Quick function to sync all tenants."""
    return QuickBooksSyncManager.sync_all_tenants(**kwargs)


def get_sync_stats(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Quick function to get sync statistics."""
    return QuickBooksSyncManager.get_sync_statistics(tenant_id)


def check_task(task_id: str) -> Dict[str, Any]:
    """Quick function to check task status."""
    return QuickBooksSyncManager.get_task_status(task_id)