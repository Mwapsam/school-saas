import logging
from datetime import timedelta
from typing import Dict, Any, Optional, List
from celery import shared_task
from django.utils import timezone
from django.core.files.storage import default_storage
from django_tenants.utils import schema_context

from core.models import Student, School, QuickBooksCustomerSync, QuickBooksSyncLog, ReportTemplate, ExamGroup, StudentReport
from core.services.quickbooks_service import QuickBooksService
from core.services.quickbooks_fee_sync_service import QuickBooksFeeSync
from core.services.report_generation_service import ReportGenerationService
from core.services.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)

# Errors that mean "reconnect QuickBooks" - retrying won't help.
_QB_NON_RETRYABLE = (
    'invalid_grant', 'invalid_client', 'unauthorized_client',
    'authentication expired', 'authentication required',
    'please reconnect', 'refresh token is invalid', 'refresh token expired',
    'not connected', 'credentials not configured',
)


def _qb_error_is_retryable(exc: Exception) -> bool:
    """True for transient QuickBooks failures (network, 429, 5xx); False for
    auth/config problems that a retry cannot fix."""
    msg = str(exc).lower()
    if any(k in msg for k in _QB_NON_RETRYABLE):
        return False
    # Explicit non-retryable HTTP statuses embedded in the SDK error string.
    for code in ('400', '401', '403', '404'):
        if f'failed: {code}' in msg or f'status {code}' in msg:
            return False
    return True


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_admitted_students_to_quickbooks(self, tenant_id: str, limit: Optional[int] = None, 
                                        force_resync: bool = False) -> Dict[str, Any]:
    start_time = timezone.now()
    
    try:
        tenant = School.objects.get(id=tenant_id)
        logger.info(f"Starting QuickBooks student sync for tenant: {tenant.name} ({tenant_id})")
        
        qb_service = QuickBooksService(tenant)
        connection_status = qb_service.get_connection_status()
        
        if not connection_status['connected']:
            error_msg = f"QuickBooks not connected for tenant {tenant.name}: {connection_status['message']}"
            logger.error(error_msg)
            return {
                'success': False,
                'tenant_id': str(tenant_id),
                'tenant_name': tenant.name,
                'error': error_msg,
                'status': connection_status['status']
            }
        
        qb_sync = QuickBooksFeeSync(tenant)
        
        students_queryset = Student.objects.filter(
            tenant=tenant,
            is_active=True,
            is_deleted=False
        ).select_related('tenant')
        
        if not force_resync:
            synced_student_ids = QuickBooksCustomerSync.objects.filter(
                tenant=tenant,
                sync_status='synced'
            ).values_list('student_id', flat=True)
            students_queryset = students_queryset.exclude(id__in=synced_student_ids)
        
        if limit:
            students_queryset = students_queryset[:limit]
        
        students = list(students_queryset)
        total_students = len(students)
        
        logger.info(f"Found {total_students} students to sync for tenant {tenant.name}")
        
        if total_students == 0:
            return {
                'success': True,
                'tenant_id': str(tenant_id),
                'tenant_name': tenant.name,
                'total_students': 0,
                'synced_students': 0,
                'failed_students': 0,
                'skipped_students': 0,
                'message': 'No students found to sync'
            }
        
        synced_students = 0
        failed_students = 0
        skipped_students = 0
        sync_errors = []
        
        for i, student in enumerate(students, 1):
            try:
                logger.info(f"Processing student {i}/{total_students}: {student.admission_no} - {student.first_name} {student.last_name}")
                
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i,
                        'total': total_students,
                        'student_name': f"{student.first_name} {student.last_name}",
                        'student_id': student.admission_no
                    }
                )
                
                customer_sync = qb_sync.sync_student_as_customer(student, force_update=force_resync)
                
                if customer_sync.sync_status == 'synced':
                    synced_students += 1
                    logger.info(f"Successfully synced student {student.admission_no} to QuickBooks customer {customer_sync.quickbooks_customer_id}")
                else:
                    failed_students += 1
                    error_msg = customer_sync.sync_error or "Unknown sync error"
                    sync_errors.append({
                        'student_id': student.admission_no,
                        'student_name': f"{student.first_name} {student.last_name}",
                        'error': error_msg
                    })
                    logger.error(f"Failed to sync student {student.admission_no}: {error_msg}")
                
            except ValidationException as e:
                failed_students += 1
                error_msg = str(e)
                sync_errors.append({
                    'student_id': student.admission_no,
                    'student_name': f"{student.first_name} {student.last_name}",
                    'error': error_msg
                })
                logger.error(f"Validation error syncing student {student.admission_no}: {error_msg}")
                
            except BusinessLogicException as e:
                if "authentication" in str(e).lower():
                    logger.error(f"Authentication error during sync: {str(e)}")
                    return {
                        'success': False,
                        'tenant_id': str(tenant_id),
                        'tenant_name': tenant.name,
                        'error': str(e),
                        'processed_students': i - 1,
                        'synced_students': synced_students,
                        'failed_students': failed_students
                    }
                else:
                    failed_students += 1
                    error_msg = str(e)
                    sync_errors.append({
                        'student_id': student.admission_no,
                        'student_name': f"{student.first_name} {student.last_name}",
                        'error': error_msg
                    })
                    logger.error(f"Business logic error syncing student {student.admission_no}: {error_msg}")
                
            except Exception as e:
                failed_students += 1
                error_msg = f"Unexpected error: {str(e)}"
                sync_errors.append({
                    'student_id': student.admission_no,
                    'student_name': f"{student.first_name} {student.last_name}",
                    'error': error_msg
                })
                logger.error(f"Unexpected error syncing student {student.admission_no}: {error_msg}")
        
        duration = (timezone.now() - start_time).total_seconds()
        
        result = {
            'success': True,
            'tenant_id': str(tenant_id),
            'tenant_name': tenant.name,
            'total_students': total_students,
            'synced_students': synced_students,
            'failed_students': failed_students,
            'skipped_students': skipped_students,
            'duration_seconds': duration,
            'errors': sync_errors[:10], 
            'message': f'Sync completed: {synced_students} synced, {failed_students} failed out of {total_students} students'
        }
        
        logger.info(f"QuickBooks sync completed for tenant {tenant.name}: {result['message']} (Duration: {duration:.2f}s)")
        return result
        
    except School.DoesNotExist:
        error_msg = f"Tenant with ID {tenant_id} not found"
        logger.error(error_msg)
        return {
            'success': False,
            'tenant_id': str(tenant_id),
            'error': error_msg
        }
        
    except Exception as e:
        error_msg = f"Unexpected error in QuickBooks sync task: {str(e)}"
        logger.error(error_msg)
        
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying QuickBooks sync task in {self.default_retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'tenant_id': str(tenant_id),
            'error': error_msg,
            'retries_exhausted': True
        }


@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def sync_all_tenants_students_to_quickbooks(self, limit_per_tenant: Optional[int] = None,
                                           force_resync: bool = False) -> Dict[str, Any]:
    start_time = timezone.now()
    
    try:
        tenants = School.objects.filter(is_active=True)
        total_tenants = tenants.count()
        
        logger.info(f"Starting QuickBooks sync for all tenants: {total_tenants} tenants found")
        
        if total_tenants == 0:
            return {
                'success': True,
                'total_tenants': 0,
                'processed_tenants': 0,
                'message': 'No active tenants found'
            }
        
        tenant_results = []
        processed_tenants = 0
        
        for i, tenant in enumerate(tenants, 1):
            try:
                logger.info(f"Processing tenant {i}/{total_tenants}: {tenant.name}")
                
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current_tenant': i,
                        'total_tenants': total_tenants,
                        'tenant_name': tenant.name,
                        'tenant_id': str(tenant.id)
                    }
                )
                
                # Run sync for this tenant directly (avoid Celery chaining)
                # Use apply() to run task synchronously with proper task context
                result = sync_admitted_students_to_quickbooks.apply(
                    args=[str(tenant.id), limit_per_tenant, force_resync]
                ).result  
                
                tenant_results.append(result)
                processed_tenants += 1
                
                logger.info(f"Completed sync for tenant {tenant.name}: {result.get('message', 'Unknown result')}")
                
            except Exception as e:
                error_msg = f"Failed to sync tenant {tenant.name}: {str(e)}"
                logger.error(error_msg)
                tenant_results.append({
                    'success': False,
                    'tenant_id': str(tenant.id),
                    'tenant_name': tenant.name,
                    'error': error_msg
                })
        
        # Calculate summary statistics
        total_students_processed = sum(r.get('total_students', 0) for r in tenant_results)
        total_students_synced = sum(r.get('synced_students', 0) for r in tenant_results)
        total_students_failed = sum(r.get('failed_students', 0) for r in tenant_results)
        
        successful_tenants = sum(1 for r in tenant_results if r.get('success', False))
        failed_tenants = total_tenants - successful_tenants
        
        duration = (timezone.now() - start_time).total_seconds()
        
        result = {
            'success': True,
            'total_tenants': total_tenants,
            'processed_tenants': processed_tenants,
            'successful_tenants': successful_tenants,
            'failed_tenants': failed_tenants,
            'total_students_processed': total_students_processed,
            'total_students_synced': total_students_synced,
            'total_students_failed': total_students_failed,
            'duration_seconds': duration,
            'tenant_results': tenant_results,
            'message': f'All-tenant sync completed: {successful_tenants}/{total_tenants} tenants successful, {total_students_synced} students synced'
        }
        
        logger.info(f"All-tenant QuickBooks sync completed: {result['message']} (Duration: {duration:.2f}s)")
        return result
        
    except Exception as e:
        error_msg = f"Unexpected error in all-tenant QuickBooks sync: {str(e)}"
        logger.error(error_msg)
        
        # Retry the task if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying all-tenant sync task in {self.default_retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'error': error_msg,
            'retries_exhausted': True
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_single_student_to_quickbooks(self, student_id: str, force_resync: bool = False) -> Dict[str, Any]:
    """
    Celery task to sync a single student to QuickBooks.
    
    Args:
        student_id: UUID of the student to sync
        force_resync: If True, will re-sync even if already synced
        
    Returns:
        Dict with sync result
    """
    start_time = timezone.now()
    
    try:
        # Get the student
        student = Student.objects.select_related('tenant').get(id=student_id)
        tenant = student.tenant
        
        logger.info(f"Starting QuickBooks sync for student: {student.admission_no} - {student.first_name} {student.last_name}")
        
        # Check if QuickBooks integration is available
        qb_service = QuickBooksService(tenant)
        connection_status = qb_service.get_connection_status()
        
        if not connection_status['connected']:
            error_msg = f"QuickBooks not connected for tenant {tenant.name}: {connection_status['message']}"
            logger.error(error_msg)
            return {
                'success': False,
                'student_id': str(student_id),
                'student_name': f"{student.first_name} {student.last_name}",
                'error': error_msg,
                'status': connection_status['status']
            }
        
        # Initialize QuickBooks sync service
        qb_sync = QuickBooksFeeSync(tenant)
        
        # Sync the student
        customer_sync = qb_sync.sync_student_as_customer(student, force_update=force_resync)
        
        duration = (timezone.now() - start_time).total_seconds()
        
        if customer_sync.sync_status == 'synced':
            result = {
                'success': True,
                'student_id': str(student_id),
                'student_name': f"{student.first_name} {student.last_name}",
                'student_admission_no': student.admission_no,
                'quickbooks_customer_id': customer_sync.quickbooks_customer_id,
                'customer_display_name': customer_sync.customer_display_name,
                'duration_seconds': duration,
                'message': f'Successfully synced student {student.admission_no} to QuickBooks'
            }
            logger.info(result['message'])
            return result
        else:
            error_msg = customer_sync.sync_error or "Unknown sync error"
            result = {
                'success': False,
                'student_id': str(student_id),
                'student_name': f"{student.first_name} {student.last_name}",
                'error': error_msg,
                'duration_seconds': duration
            }
            logger.error(f"Failed to sync student {student.admission_no}: {error_msg}")
            return result
            
    except Student.DoesNotExist:
        error_msg = f"Student with ID {student_id} not found"
        logger.error(error_msg)
        return {
            'success': False,
            'student_id': str(student_id),
            'error': error_msg
        }
        
    except Exception as e:
        error_msg = f"Unexpected error syncing student: {str(e)}"
        logger.error(error_msg)
        
        # Retry the task if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying student sync task in {self.default_retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'student_id': str(student_id),
            'error': error_msg,
            'retries_exhausted': True
        }


@shared_task
def cleanup_failed_quickbooks_syncs(days_old: int = 7) -> Dict[str, Any]:
    """
    Celery task to clean up old failed QuickBooks sync records.
    
    Args:
        days_old: Number of days old for sync records to be considered for cleanup
        
    Returns:
        Dict with cleanup results
    """
    cutoff_date = timezone.now() - timedelta(days=days_old)
    
    try:
        # Clean up failed customer syncs
        failed_syncs = QuickBooksCustomerSync.objects.filter(
            sync_status='failed',
            created_at__lt=cutoff_date
        )
        
        deleted_count = failed_syncs.count()
        failed_syncs.delete()
        
        # Clean up old sync logs
        old_logs = QuickBooksSyncLog.objects.filter(
            status='failed',
            created_at__lt=cutoff_date
        )
        
        deleted_logs_count = old_logs.count()
        old_logs.delete()
        
        logger.info(f"Cleaned up {deleted_count} failed sync records and {deleted_logs_count} old sync logs")
        
        return {
            'success': True,
            'deleted_sync_records': deleted_count,
            'deleted_log_records': deleted_logs_count,
            'cutoff_date': cutoff_date.isoformat(),
            'message': f'Cleanup completed: removed {deleted_count} sync records and {deleted_logs_count} log records older than {days_old} days'
        }
        
    except Exception as e:
        error_msg = f"Error during QuickBooks sync cleanup: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def proactive_quickbooks_token_refresh(self) -> Dict[str, Any]:
    """
    Proactively refresh QuickBooks tokens that will expire soon.
    
    This task runs periodically to refresh tokens before they expire,
    preventing authentication failures during critical operations.
    
    Returns:
        Dict with refresh results for all tenants
    """
    from core.models import School, QuickBooksIntegration
    from core.services.quickbooks_service import QuickBooksService
    
    start_time = timezone.now()
    
    try:
        logger.info("Starting proactive QuickBooks token refresh for all tenants")
        
        # Find all connected QuickBooks integrations that need token refresh
        integrations_needing_refresh = QuickBooksIntegration.objects.filter(
            is_connected=True,
            access_token__isnull=False,
            refresh_token__isnull=False
        ).select_related('tenant')
        
        # Filter to those that need refresh (within 10 minutes of expiry)
        integrations_to_refresh = []
        for integration in integrations_needing_refresh:
            if integration.needs_refresh():
                integrations_to_refresh.append(integration)
        
        total_integrations = len(integrations_to_refresh)
        logger.info(f"Found {total_integrations} QuickBooks integrations that need token refresh")
        
        if total_integrations == 0:
            return {
                'success': True,
                'total_integrations': 0,
                'refreshed_integrations': 0,
                'failed_integrations': 0,
                'message': 'No integrations need token refresh at this time'
            }
        
        refresh_results = []
        refreshed_count = 0
        failed_count = 0
        
        for i, integration in enumerate(integrations_to_refresh, 1):
            try:
                tenant = integration.tenant
                logger.info(f"Refreshing tokens for tenant {tenant.name} ({i}/{total_integrations})")
                
                # Update task progress
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i,
                        'total': total_integrations,
                        'tenant_name': tenant.name,
                        'tenant_id': str(tenant.id)
                    }
                )
                
                qb_service = QuickBooksService(tenant)
                refreshed_integration = qb_service.refresh_token()
                
                refreshed_count += 1
                refresh_results.append({
                    'tenant_id': str(tenant.id),
                    'tenant_name': tenant.name,
                    'success': True,
                    'time_until_expiry_minutes': int(refreshed_integration.time_until_expiry().total_seconds() / 60) if refreshed_integration.time_until_expiry() else None,
                    'message': f'Token refreshed successfully'
                })
                
                logger.info(f"Successfully refreshed tokens for tenant {tenant.name}")
                
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                refresh_results.append({
                    'tenant_id': str(integration.tenant.id),
                    'tenant_name': integration.tenant.name,
                    'success': False,
                    'error': error_msg
                })
                
                logger.error(f"Failed to refresh tokens for tenant {integration.tenant.name}: {error_msg}")
        
        duration = (timezone.now() - start_time).total_seconds()
        
        result = {
            'success': True,
            'total_integrations': total_integrations,
            'refreshed_integrations': refreshed_count,
            'failed_integrations': failed_count,
            'duration_seconds': duration,
            'refresh_results': refresh_results,
            'message': f'Proactive token refresh completed: {refreshed_count} successful, {failed_count} failed out of {total_integrations} integrations'
        }
        
        logger.info(f"Proactive token refresh completed: {result['message']} (Duration: {duration:.2f}s)")
        return result
        
    except Exception as e:
        error_msg = f"Unexpected error in proactive token refresh: {str(e)}"
        logger.error(error_msg)
        
        # Retry the task if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying proactive token refresh in {self.default_retry_delay} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'error': error_msg,
            'retries_exhausted': True
        }


@shared_task
def check_quickbooks_token_health() -> Dict[str, Any]:
    """
    Check the health of all QuickBooks token integrations and report status.
    
    This task provides monitoring and alerting capabilities for QuickBooks integrations.
    
    Returns:
        Dict with health check results
    """
    from core.models import School, QuickBooksIntegration
    from core.services.quickbooks_service import QuickBooksService
    
    try:
        logger.info("Starting QuickBooks token health check")
        
        all_integrations = QuickBooksIntegration.objects.filter(
            is_connected=True
        ).select_related('tenant')
        
        health_results = {
            'total_integrations': all_integrations.count(),
            'healthy_integrations': 0,
            'expiring_soon': 0,  # Within 1 hour
            'expired_tokens': 0,
            'missing_refresh_tokens': 0,
            'connection_issues': 0,
            'details': []
        }
        
        for integration in all_integrations:
            try:
                tenant = integration.tenant
                qb_service = QuickBooksService(tenant)
                
                # Check token health
                detail = {
                    'tenant_id': str(tenant.id),
                    'tenant_name': tenant.name,
                    'is_connected': integration.is_connected,
                    'has_access_token': bool(integration.access_token),
                    'has_refresh_token': bool(integration.refresh_token),
                    'token_expires_at': integration.token_expires_at.isoformat() if integration.token_expires_at else None,
                    'time_until_expiry_minutes': None,
                    'status': 'unknown'
                }
                
                if integration.time_until_expiry():
                    time_until_expiry = integration.time_until_expiry().total_seconds() / 60
                    detail['time_until_expiry_minutes'] = int(time_until_expiry)
                    
                    if time_until_expiry <= 0:
                        health_results['expired_tokens'] += 1
                        detail['status'] = 'expired'
                    elif time_until_expiry <= 60:  # Within 1 hour
                        health_results['expiring_soon'] += 1
                        detail['status'] = 'expiring_soon'
                    else:
                        health_results['healthy_integrations'] += 1
                        detail['status'] = 'healthy'
                else:
                    detail['status'] = 'no_expiry_info'
                    health_results['connection_issues'] += 1
                
                if not integration.refresh_token:
                    health_results['missing_refresh_tokens'] += 1
                    detail['status'] = 'missing_refresh_token'
                
                # Test connection if token should be valid
                if detail['status'] == 'healthy':
                    try:
                        connection_test = qb_service.test_connection()
                        detail['connection_test'] = connection_test['success']
                        if not connection_test['success']:
                            health_results['connection_issues'] += 1
                            detail['status'] = 'connection_failed'
                            detail['connection_error'] = connection_test['message']
                    except Exception as e:
                        detail['connection_test'] = False
                        detail['connection_error'] = str(e)
                        health_results['connection_issues'] += 1
                        detail['status'] = 'connection_failed'
                
                health_results['details'].append(detail)
                
            except Exception as e:
                logger.error(f"Error checking health for integration {integration.id}: {str(e)}")
                health_results['connection_issues'] += 1
                health_results['details'].append({
                    'tenant_id': str(integration.tenant.id),
                    'tenant_name': integration.tenant.name,
                    'status': 'health_check_failed',
                    'error': str(e)
                })
        
        # Generate summary message
        summary_parts = []
        if health_results['healthy_integrations'] > 0:
            summary_parts.append(f"{health_results['healthy_integrations']} healthy")
        if health_results['expiring_soon'] > 0:
            summary_parts.append(f"{health_results['expiring_soon']} expiring soon")
        if health_results['expired_tokens'] > 0:
            summary_parts.append(f"{health_results['expired_tokens']} expired")
        if health_results['connection_issues'] > 0:
            summary_parts.append(f"{health_results['connection_issues']} with issues")
            
        health_results['summary'] = f"QuickBooks integrations: {', '.join(summary_parts) if summary_parts else 'none active'}"
        
        logger.info(f"QuickBooks health check completed: {health_results['summary']}")
        
        return {
            'success': True,
            **health_results
        }
        
    except Exception as e:
        error_msg = f"Error during QuickBooks health check: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }


@shared_task
def retry_failed_quickbooks_fee_syncs(days_back: int = 3) -> Dict[str, Any]:
    """Re-dispatch the fee-sync tasks for rows still failed/pending within the
    last ``days_back`` days. Safety net so a transient QuickBooks outage that
    outlasts a task's own retries is still picked up (the per-task idempotency
    guards make re-dispatch a no-op once a row has since synced)."""
    from core.models import (
        QuickBooksFeeInvoiceLineSync, QuickBooksFeePaymentSync, QuickBooksFeeInvoiceSync,
    )
    from core.signals import is_quickbooks_enabled

    cutoff = timezone.now() - timedelta(days=days_back)
    totals = {'charges': 0, 'payments': 0, 'resyncs': 0, 'tenants': 0,
              'needs_review': 0}
    review_by_tenant = {}

    for tenant in School.objects.exclude(schema_name='public'):
        with schema_context(tenant.schema_name):
            if not is_quickbooks_enabled(tenant):
                continue
            totals['tenants'] += 1
            tid = str(tenant.id)

            review_count = (
                QuickBooksFeeInvoiceSync.objects.filter(tenant=tenant, needs_review=True).count()
                + QuickBooksFeePaymentSync.objects.filter(tenant=tenant, needs_review=True).count()
                + QuickBooksFeeInvoiceLineSync.objects.filter(tenant=tenant, needs_review=True).count()
            )
            if review_count:
                review_by_tenant[tenant.schema_name] = review_count
                totals['needs_review'] += review_count

            charges = QuickBooksFeeInvoiceLineSync.objects.filter(
                tenant=tenant, sync_status__in=['failed', 'draft'],
                finance_fee__isnull=False, updated_at__gte=cutoff,
            ).values_list('finance_fee_id', flat=True)
            for fee_id in charges:
                sync_fee_charge_to_quickbooks.delay(tid, str(fee_id))
                totals['charges'] += 1

            payments = QuickBooksFeePaymentSync.objects.filter(
                tenant=tenant, sync_status__in=['failed', 'pending'],
                fee_transaction__isnull=False, updated_at__gte=cutoff,
            ).values_list('fee_transaction_id', flat=True)
            for ft_id in payments:
                sync_fee_payment_to_quickbooks.delay(tid, str(ft_id))
                totals['payments'] += 1

            resyncs = QuickBooksFeeInvoiceSync.objects.filter(
                tenant=tenant, sync_status='failed',
                family_invoice__isnull=False, updated_at__gte=cutoff,
            ).values_list('family_invoice_id', flat=True)
            for inv_id in resyncs:
                resync_fee_invoice_to_quickbooks.delay(tid, str(inv_id))
                totals['resyncs'] += 1

    logger.info(f"retry_failed_quickbooks_fee_syncs re-dispatched {totals}")
    if review_by_tenant:
        logger.warning(
            "QuickBooks: %d sync row(s) need manual review: %s",
            totals['needs_review'], review_by_tenant,
        )
    return {'success': True, 'needs_review_by_tenant': review_by_tenant, **totals}


logger = logging.getLogger(__name__)


# =====================================================
# REPORT GENERATION TASKS
# =====================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_student_report_task(self, tenant_id: str, student_id: str, template_id: str, exam_group_id: str) -> Dict[str, Any]:
    """Background task to generate a single student report"""
    start_time = timezone.now()

    try:
        # Fetch tenant in public schema
        tenant = School.objects.get(id=tenant_id)
        logger.info(f"Starting report generation for student {student_id} in tenant: {tenant.name}")

        # CRITICAL: All tenant-specific queries must run inside schema_context
        with schema_context(tenant.schema_name):
            report_service = ReportGenerationService(tenant=tenant)
            report = report_service.generate_student_report(
                student_id=student_id,
                template_id=template_id,
                exam_group_id=exam_group_id
            )
        
        duration = (timezone.now() - start_time).total_seconds()
        logger.info(f"Successfully generated report for student {student_id} in {duration:.2f} seconds")
        
        return {
            'success': True, 'tenant_id': tenant_id, 'student_id': student_id,
            'report_id': str(report.id), 'pdf_path': report.pdf_file_path,
            'html_path': report.html_file_path, 'generation_status': report.generation_status,
            'duration_seconds': duration
        }
        
    except School.DoesNotExist:
        error_msg = f"Tenant {tenant_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg, 'tenant_id': tenant_id, 'student_id': student_id}
        
    except Exception as e:
        error_msg = f"Error generating report for student {student_id}: {str(e)}"
        logger.error(error_msg)
        
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying report generation for student {student_id} (attempt {self.request.retries + 2})")
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'success': False, 'error': error_msg, 'tenant_id': tenant_id, 'student_id': student_id, 'retries_exhausted': True}


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def bulk_generate_reports_task(self, tenant_id: str, template_id: str, exam_group_id: str,
                              student_ids: Optional[List[str]] = None,
                              section_overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Background task to generate reports for a CHUNK of students.
    NOTE: The underlying service must process these SEQUENTIALLY. 
    Do NOT use ThreadPoolExecutor inside the service when called from Celery."""
    start_time = timezone.now()

    try:
        tenant = School.objects.get(id=tenant_id)
        logger.info(f"Starting bulk report generation for {len(student_ids) if student_ids else 'all'} students in tenant: {tenant.name}")

        with schema_context(tenant.schema_name):
            report_service = ReportGenerationService(tenant=tenant)
            results = report_service.bulk_generate_reports(
                template_id=template_id,
                exam_group_id=exam_group_id,
                student_ids=student_ids,
                section_overrides=section_overrides,
            )
        
        duration = (timezone.now() - start_time).total_seconds()
        logger.info(f"Bulk report generation completed for {results['total_students']} students in {duration:.2f} seconds")
        
        return {
            'success': True, 'tenant_id': tenant_id, 'template_id': template_id,
            'exam_group_id': exam_group_id, 'duration_seconds': duration, **results
        }
        
    except School.DoesNotExist:
        error_msg = f"Tenant {tenant_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg, 'tenant_id': tenant_id}
        
    except Exception as e:
        error_msg = f"Error in bulk report generation for tenant {tenant_id}: {str(e)}"
        logger.error(error_msg)
        
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying bulk report generation (attempt {self.request.retries + 2})")
            raise self.retry(exc=e, countdown=120 * (self.request.retries + 1))
        
        return {'success': False, 'error': error_msg, 'tenant_id': tenant_id, 'retries_exhausted': True}


@shared_task(bind=True)
def generate_reports_on_exam_publish(self, tenant_id: str, exam_group_id: str) -> Dict[str, Any]:
    """Task triggered when exam results are published to auto-generate reports.
    OPTIMIZATION: Chunks students into smaller batches to prevent Celery worker timeouts and OOM errors."""
    start_time = timezone.now()
    
    try:
        tenant = School.objects.get(id=tenant_id)
        
        # CRITICAL FIX: Wrap tenant-specific queries in schema_context
        with schema_context(tenant.schema_name):
            exam_group = ExamGroup.objects.get(id=exam_group_id, tenant=tenant)
            templates = ReportTemplate.objects.filter(
                tenant=tenant, batch=exam_group.batch, is_active=True
            )
            
            if not templates.exists():
                logger.warning(f"No active report templates found for batch {exam_group.batch.name}")
                return {'success': True, 'message': 'No applicable templates found', 'templates_found': 0}
            
            template_results = []
            CHUNK_SIZE = 50  # Process 50 students per Celery task to keep memory footprint low
            
            for template in templates:
                # Fetch student IDs for this specific template's batch
                student_ids = list(
                    Student.objects.filter(
                        tenant=tenant, is_active=True,
                        batchstudent__batch=template.batch, 
                        batchstudent__is_active=True
                    ).values_list('id', flat=True).distinct()
                )
                
                # Enqueue a separate task for each chunk of students
                for i in range(0, len(student_ids), CHUNK_SIZE):
                    chunk = [str(sid) for sid in student_ids[i:i + CHUNK_SIZE]]
                    
                    task_result = bulk_generate_reports_task.delay(
                        tenant_id=tenant_id,
                        template_id=str(template.id),
                        exam_group_id=exam_group_id,
                        student_ids=chunk  # Pass only the chunk!
                    )
                    
                    template_results.append({
                        'template_id': str(template.id),
                        'template_name': template.name,
                        'task_id': task_result.id,
                        'students_in_chunk': len(chunk)
                    })
        
        duration = (timezone.now() - start_time).total_seconds()
        logger.info(f"Initiated {len(template_results)} chunked tasks for {len(templates)} templates in {duration:.2f} seconds")
        
        return {
            'success': True, 'tenant_id': tenant_id, 'exam_group_id': exam_group_id,
            'templates_processed': len(templates), 'total_chunks_created': len(template_results),
            'template_results': template_results, 'duration_seconds': duration
        }
        
    except (School.DoesNotExist, ExamGroup.DoesNotExist) as e:
        return {'success': False, 'error': f"Required object not found: {str(e)}", 'tenant_id': tenant_id}
    except Exception as e:
        return {'success': False, 'error': f"Error auto-generating reports: {str(e)}", 'tenant_id': tenant_id}


@shared_task
def cleanup_old_report_files(days_old: int = 30) -> Dict[str, Any]:
    """Clean up old report files to save storage space.
    OPTIMIZATION: Uses .iterator() and bulk_update() to handle massive datasets without OOM."""
    start_time = timezone.now()
    
    try:
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # OPTIMIZATION: Use .only() and .iterator() to stream records without loading them all into RAM
        old_reports = StudentReport.objects.filter(
            generation_completed_at__lt=cutoff_date,
            generation_status='completed'
        ).exclude(
            pdf_file_path__isnull=True, html_file_path__isnull=True
        ).only('id', 'pdf_file_path', 'html_file_path').iterator(chunk_size=1000)
        
        cleaned_files = 0
        errors = []
        reports_to_update = []
        total_processed = 0
        
        logger.info(f"Starting cleanup of old report files (older than {days_old} days)")
        
        for report in old_reports:
            total_processed += 1
            try:
                # Remove PDF file
                if report.pdf_file_path and default_storage.exists(report.pdf_file_path):
                    default_storage.delete(report.pdf_file_path)
                    cleaned_files += 1
                
                # Remove HTML file
                if report.html_file_path and default_storage.exists(report.html_file_path):
                    default_storage.delete(report.html_file_path)
                    cleaned_files += 1
                
                # Clear file paths from memory object
                report.pdf_file_path = None
                report.html_file_path = None
                reports_to_update.append(report)
                
                # OPTIMIZATION: Batch update the database every 500 records to minimize DB hits
                if len(reports_to_update) >= 500:
                    StudentReport.objects.bulk_update(reports_to_update, ['pdf_file_path', 'html_file_path'])
                    reports_to_update = []  # Reset batch
                    
            except Exception as e:
                error_msg = f"Error cleaning files for report {report.id}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Final batch update for any remaining records
        if reports_to_update:
            StudentReport.objects.bulk_update(reports_to_update, ['pdf_file_path', 'html_file_path'])
        
        duration = (timezone.now() - start_time).total_seconds()
        logger.info(f"Cleanup completed: {cleaned_files} files cleaned from {total_processed} reports in {duration:.2f} seconds")
        
        return {
            'success': True, 'reports_processed': total_processed, 'files_cleaned': cleaned_files,
            'errors': errors, 'duration_seconds': duration, 'cutoff_days': days_old
        }
        
    except Exception as e:
        logger.error(f"Error during report file cleanup: {str(e)}")
        return {'success': False, 'error': str(e), 'cutoff_days': days_old}


@shared_task(bind=True, max_retries=1, default_retry_delay=60)
def build_reports_zip_task(self, tenant_id: str, job_id: str, report_ids: List[str]) -> Dict[str, Any]:
    """Background task to build a ZIP file of selected report PDFs.
    Updates the ReportZipJob progress and stores the result in media storage."""
    from core.models import ReportZipJob, StudentReport, School
    from django.core.files.storage import default_storage
    import zipfile
    import io

    job = None  # Initialize to avoid NameError in except clause if exception occurs before job is fetched

    try:
        tenant = School.objects.get(id=tenant_id)
    except School.DoesNotExist:
        logger.error(f"Tenant {tenant_id} not found")
        return {'success': False, 'error': 'tenant not found', 'job_id': job_id}

    try:
        with schema_context(tenant.schema_name):
            # Fetch job within schema_context to ensure proper tenant isolation
            try:
                job = ReportZipJob.objects.get(id=job_id, tenant=tenant)
            except ReportZipJob.DoesNotExist:
                logger.error(f"Job {job_id} not found in tenant {tenant_id}")
                return {'success': False, 'error': 'job not found', 'job_id': job_id}
            job.status = 'processing'
            job.save(update_fields=['status'])

            # Fetch all requested reports and validate they exist
            reports = StudentReport.objects.filter(
                id__in=report_ids, generation_status='completed'
            ).only('id', 'pdf_file_path', 'student__admission_no').iterator(chunk_size=100)

            # Build ZIP in memory first, then write to storage
            zip_buffer = io.BytesIO()
            processed = 0
            failed = 0

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for idx, report in enumerate(reports, 1):
                    try:
                        if report.pdf_file_path and default_storage.exists(report.pdf_file_path):
                            # Read PDF from storage using context manager to avoid file handle leak
                            with default_storage.open(report.pdf_file_path, 'rb') as f:
                                pdf_content = f.read()
                            # Generate safe archive name
                            archive_name = f"report_{report.student.admission_no}_{report.id}.pdf"
                            zf.writestr(archive_name, pdf_content)
                            processed += 1
                        else:
                            failed += 1
                    except Exception as e:
                        logger.warning(f"Error adding report {report.id} to ZIP: {e}")
                        failed += 1

                    # Update progress every 10 reports to avoid excessive database writes
                    if idx % 10 == 0:
                        job.processed_reports = processed + failed
                        job.save(update_fields=['processed_reports'])

            # Update progress one final time with total count
            job.processed_reports = processed + failed
            job.save(update_fields=['processed_reports'])

            # Seek to beginning of buffer before saving (ZipFile context closed, position at end)
            zip_buffer.seek(0)

            # Write ZIP to storage and capture actual saved filename
            zip_filename = f"report_zips/{tenant.schema_name}/{job_id}.zip"
            actual_filename = default_storage.save(zip_filename, zip_buffer)

            # Update job as completed (use actual saved filename in case storage backend modified it)
            job.status = 'completed'
            job.file_path = actual_filename
            job.save(update_fields=['status', 'file_path'])

            logger.info(
                f"ZIP job {job_id} completed: {processed} reports added, {failed} failed"
            )

            return {
                'success': True,
                'job_id': job_id,
                'file_path': zip_filename,
                'reports_processed': processed,
                'reports_failed': failed,
            }

    except Exception as e:
        error_msg = f"Error building ZIP for job {job_id}: {str(e)}"
        logger.error(error_msg)

        # Only update job status if job was successfully fetched (not None)
        if job is not None:
            job.status = 'failed'
            job.error_message = error_msg
            job.save(update_fields=['status', 'error_message'])

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying ZIP build (attempt {self.request.retries + 2})")
            raise self.retry(exc=e, countdown=60)

        return {'success': False, 'error': error_msg, 'job_id': job_id}


@shared_task
def cleanup_old_zip_files(days_old: int = 1) -> Dict[str, Any]:
    """Clean up expired ZIP files and their job records across all tenants."""
    from core.models import ReportZipJob
    from django.core.files.storage import default_storage

    try:
        cutoff_date = timezone.now() - timedelta(days=days_old)
        total_deleted = 0

        # Iterate over all tenants and clean up within each schema
        for tenant in School.objects.all():
            try:
                with schema_context(tenant.schema_name):
                    # Find expired jobs within this tenant's schema
                    expired_jobs = ReportZipJob.objects.filter(
                        expires_at__lt=cutoff_date
                    ).only('id', 'file_path')

                    deleted_count = 0
                    for job in expired_jobs:
                        try:
                            # Delete ZIP file from storage if it exists
                            if job.file_path and default_storage.exists(job.file_path):
                                default_storage.delete(job.file_path)
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(f"Error deleting ZIP file {job.file_path}: {e}")

                    # Delete job records
                    expired_jobs.delete()
                    total_deleted += deleted_count
                    logger.info(
                        f"Cleaned up {deleted_count} expired ZIP jobs for tenant {tenant.name}"
                    )

            except Exception as e:
                logger.error(f"Error cleaning up ZIP files for tenant {tenant.name}: {e}")
                continue

        logger.info(f"Total cleaned up {total_deleted} expired ZIP jobs across all tenants")
        return {
            'success': True,
            'jobs_cleaned': total_deleted,
            'cutoff_days': days_old,
        }

    except Exception as e:
        logger.error(f"Error cleaning up old ZIP files: {str(e)}")
        return {'success': False, 'error': str(e)}

# ---------------------------------------------------------------------------
# Phase 7 — sync the consolidated fee ledger to QuickBooks (invoices + payments).
# Fired asynchronously (transaction.on_commit) by FinanceService so a QB outage
# never blocks or rolls back a local fee operation. Both tasks are idempotent
# and gated by the tenant's QuickBooks connection + configuration.
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_fee_charge_to_quickbooks(self, tenant_id: str, finance_fee_id: str) -> Dict[str, Any]:
    """Mirror a local FinanceFee charge as a line on the guardian's
    consolidated QuickBooks invoice (one invoice per guardian per year)."""
    from core.models import FinanceFee, FamilyInvoiceLine, QuickBooksFeeInvoiceLineSync, QuickBooksConfiguration
    from core.signals import is_quickbooks_enabled

    try:
        tenant = School.objects.get(id=tenant_id)
    except School.DoesNotExist:
        return {'success': False, 'error': 'tenant not found'}

    if not is_quickbooks_enabled(tenant):
        return {'success': False, 'skipped': 'quickbooks_disabled'}

    config = QuickBooksConfiguration.objects.filter(tenant=tenant).first()
    if config is not None and not config.auto_sync_invoices:
        return {'success': False, 'skipped': 'auto_sync_invoices_off'}

    fee = FinanceFee.objects.filter(id=finance_fee_id, tenant=tenant).select_related(
        'student', 'fee_category', 'academic_year'
    ).first()
    if fee is None:
        return {'success': False, 'error': 'finance_fee not found'}

    # Idempotency: one QB invoice line per charge.
    if QuickBooksFeeInvoiceLineSync.objects.filter(tenant=tenant, finance_fee=fee, sync_status='synced').exists():
        return {'success': True, 'skipped': 'already_synced'}

    family_invoice_line = FamilyInvoiceLine.objects.filter(
        tenant=tenant, finance_fee=fee
    ).select_related('invoice', 'invoice__guardian', 'invoice__academic_year').first()
    if family_invoice_line is None:
        return {'success': False, 'skipped': 'no_local_invoice_line'}

    try:
        sync = QuickBooksFeeSync(tenant).upsert_family_invoice_sync(family_invoice_line)
        return {'success': True, 'invoice_line_sync_id': str(sync.id)}
    except Exception as e:
        logger.error(f"QB charge sync failed for fee {finance_fee_id}: {e}")
        if _qb_error_is_retryable(e) and self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_fee_payment_to_quickbooks(self, tenant_id: str, fee_transaction_id: str) -> Dict[str, Any]:
    """Create a QuickBooks payment mirroring a local payment FeeTransaction,
    applied to the matching academic year's invoice."""
    from core.models import FeeTransaction, QuickBooksFeePaymentSync, QuickBooksConfiguration
    from core.signals import is_quickbooks_enabled

    try:
        tenant = School.objects.get(id=tenant_id)
    except School.DoesNotExist:
        return {'success': False, 'error': 'tenant not found'}

    if not is_quickbooks_enabled(tenant):
        return {'success': False, 'skipped': 'quickbooks_disabled'}

    config = QuickBooksConfiguration.objects.filter(tenant=tenant).first()
    if config is not None and not config.auto_sync_payments:
        return {'success': False, 'skipped': 'auto_sync_payments_off'}

    ft = FeeTransaction.objects.filter(
        id=fee_transaction_id, tenant=tenant, transaction_type='payment',
    ).select_related('student', 'fee_category', 'academic_year').first()
    if ft is None:
        return {'success': False, 'error': 'payment ledger row not found'}

    # Idempotency: one payment sync per ledger row.
    if QuickBooksFeePaymentSync.objects.filter(tenant=tenant, fee_transaction=ft).exists():
        return {'success': True, 'skipped': 'already_synced'}

    try:
        sync = QuickBooksFeeSync(tenant).create_fee_payment_sync(
            student=ft.student, amount=ft.amount,
            payment_date=ft.transaction_date.date() if hasattr(ft.transaction_date, 'date') else ft.transaction_date,
            payment_method=ft.payment_method, reference_number=ft.reference_number,
            fee_transaction=ft,
        )
        return {'success': True, 'payment_sync_id': str(sync.id)}
    except Exception as e:
        logger.error(f"QB payment sync failed for ledger row {fee_transaction_id}: {e}")
        if _qb_error_is_retryable(e) and self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def resync_fee_invoice_to_quickbooks(self, tenant_id: str, family_invoice_id: str) -> Dict[str, Any]:
    """Re-push a linked consolidated invoice to QuickBooks after a local
    correction (discount / fine / waiver / reversal / charge removal) changed a
    FinanceFee balance without going through the charge or payment path."""
    from core.models import FamilyInvoice, QuickBooksConfiguration
    from core.signals import is_quickbooks_enabled

    try:
        tenant = School.objects.get(id=tenant_id)
    except School.DoesNotExist:
        return {'success': False, 'error': 'tenant not found'}

    if not is_quickbooks_enabled(tenant):
        return {'success': False, 'skipped': 'quickbooks_disabled'}

    config = QuickBooksConfiguration.objects.filter(tenant=tenant).first()
    if config is not None and not config.auto_sync_invoices:
        return {'success': False, 'skipped': 'auto_sync_invoices_off'}

    fi = FamilyInvoice.objects.filter(id=family_invoice_id, tenant=tenant).first()
    if fi is None:
        return {'success': False, 'error': 'family_invoice not found'}

    try:
        header = QuickBooksFeeSync(tenant).resync_family_invoice(fi)
        if header is None:
            return {'success': True, 'skipped': 'not_linked'}
        return {'success': True, 'invoice_sync_id': str(header.id)}
    except Exception as e:
        logger.error(f"QB invoice resync failed for {family_invoice_id}: {e}")
        if _qb_error_is_retryable(e) and self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'success': False, 'error': str(e)}


# ---------------------------------------------------------------------------
# QuickBooks webhooks - reacts to changes made directly in QuickBooks (not via
# Pinewood). Never mutates the local ledger: flags the affected sync row with
# needs_review=True for staff to investigate, preserving the same "Pinewood
# is the source of truth, compensating entries only" discipline FinanceService
# enforces everywhere else. Dispatched from core.webhooks.QuickBooksWebhookView.
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def process_quickbooks_webhook_event(
    self, realm_id: str, entity_name: str, entity_id: str,
    operation: str, last_updated: str = None,
) -> Dict[str, Any]:
    from django_tenants.utils import schema_context
    from core.models import (
        QuickBooksRealmMapping, QuickBooksCustomerSync, QuickBooksFeeInvoiceSync,
        QuickBooksFeePaymentSync, QuickBooksSyncLog,
    )

    mapping = QuickBooksRealmMapping.objects.filter(realm_id=realm_id).select_related('tenant').first()
    if mapping is None:
        logger.warning(f"QuickBooks webhook for unknown realm {realm_id} ({entity_name} {entity_id}); ignoring")
        return {'success': False, 'skipped': 'unknown_realm'}

    tenant = mapping.tenant

    with schema_context(tenant.schema_name):
        def _log(status, details, error=None):
            try:
                # QuickBooksSyncLog.object_id is a local-row UUID (not used
                # here); the QuickBooks entity id goes in quickbooks_id/details.
                QuickBooksSyncLog.objects.create(
                    tenant=tenant, sync_type=entity_name.lower(), action_type='sync',
                    status=status, object_type=entity_name,
                    quickbooks_id=entity_id,
                    details={'operation': operation, 'last_updated': last_updated, **(details or {})},
                    error_message=error,
                )
            except Exception:
                logger.exception("Failed to write QuickBooksSyncLog for webhook event")

        flagging_ops = {'Delete', 'Void', 'Merge'}

        if entity_name == 'Invoice':
            sync = QuickBooksFeeInvoiceSync.objects.filter(
                tenant=tenant, quickbooks_invoice_id=entity_id,
            ).first()
            if sync is None:
                _log('partial', {'reason': 'no_matching_local_invoice_sync'})
                return {'success': True, 'flagged': False, 'reason': 'no_local_match'}
            if operation in flagging_ops:
                sync.needs_review = True
                sync.review_note = f"QuickBooks reported '{operation}' on this invoice - verify against local FamilyInvoice before taking any action."
                sync.save(update_fields=['needs_review', 'review_note'])
                _log('partial', {'flagged': True})
            else:
                _log('success', {'flagged': False})
            return {'success': True, 'flagged': operation in flagging_ops}

        if entity_name == 'Payment':
            sync = QuickBooksFeePaymentSync.objects.filter(
                tenant=tenant, quickbooks_payment_id=entity_id,
            ).first()
            if sync is None:
                # A payment with zero Pinewood footprint - most important case
                # to surface, since money may have moved with no local record.
                _log('partial', {'reason': 'payment_recorded_in_quickbooks_with_no_local_match'})
                return {'success': True, 'flagged': False, 'reason': 'no_local_match'}
            if operation in flagging_ops or operation == 'Update':
                sync.needs_review = True
                sync.review_note = f"QuickBooks reported '{operation}' on this payment - verify against the local FeeTransaction ledger."
                sync.save(update_fields=['needs_review', 'review_note'])
                _log('partial', {'flagged': True})
            else:
                _log('success', {'flagged': False})
            return {'success': True, 'flagged': True}

        if entity_name == 'Customer':
            sync = QuickBooksCustomerSync.objects.filter(
                tenant=tenant, quickbooks_customer_id=entity_id,
            ).first()
            if sync is None:
                _log('partial', {'reason': 'no_matching_local_customer_sync'})
                return {'success': True, 'flagged': False, 'reason': 'no_local_match'}
            if operation in flagging_ops:
                sync.needs_review = True
                sync.review_note = f"QuickBooks reported '{operation}' on this customer - the guardian's QuickBooks mapping may now be broken."
                sync.save(update_fields=['needs_review', 'review_note'])
                _log('partial', {'flagged': True})
            else:
                # Cosmetic update (name/contact info) - log only, no review needed.
                _log('success', {'flagged': False})
            return {'success': True, 'flagged': operation in flagging_ops}

        return {'success': False, 'error': f'unhandled entity type {entity_name}'}


@shared_task
def notify_fee_due(tenant_id: Optional[str] = None):
    """Thin wrapper so ``notify_fee_due`` can run on Celery beat. See the
    management command of the same name for the logic."""
    from django.core.management import call_command
    args = []
    if tenant_id:
        args += ['--tenant-id', str(tenant_id)]
    call_command('notify_fee_due', *args)
    return {'success': True}


@shared_task
def hr_generate_tasks() -> Dict[str, Any]:
    """Nightly HR housekeeping across every tenant:

    * refresh ``EmployeeContract.renewal_status`` for un-pinned dated contracts
    * (re)generate auto :class:`core.models.HRTask` reminders for contract
      expiry, probation end and document expiry (idempotent via ``dedupe_key``)
    """
    from core.services.hr_contract_service import ContractService
    from core.services.hr_task_service import HRTaskService

    totals = {'tenants': 0, 'contracts_refreshed': 0, 'tasks_created': 0}
    for tenant in School.objects.exclude(schema_name='public'):
        try:
            with schema_context(tenant.schema_name):
                totals['contracts_refreshed'] += ContractService(tenant).refresh_statuses()
                totals['tasks_created'] += HRTaskService(tenant).generate_from_rules()
                totals['tenants'] += 1
        except Exception as exc:  # one tenant failing must not stop the rest
            logger.error("hr_generate_tasks failed for tenant %s: %s", tenant.name, exc)
            continue
    logger.info("hr_generate_tasks: %s", totals)
    return {'success': True, **totals}
