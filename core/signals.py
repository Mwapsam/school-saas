import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from datetime import date

from .models import Student, BatchStudent, BatchFeeCategory, BatchFeeCategoryStudent, FinanceFee
from .services.quickbooks_service import QuickBooksService
from .services.finance_service import FinanceService
from core.services.exceptions import ValidationException
from core.utils.model_field_validator import get_student_quickbooks_data, validate_student_fields_for_quickbooks

logger = logging.getLogger(__name__)

try:
    from quickbooks.accounts import (
        Customer, EmailAddr, TelephoneNumber, PhysicalAddr,
        QuickBooksCustomerManager
    )
    QUICKBOOKS_AVAILABLE = True
except ImportError as _qb_import_err:
    QUICKBOOKS_AVAILABLE = False
    # Make silent disablement visible at startup — QB features will be inert.
    logger.warning(
        "QuickBooks SDK module not importable (%s); QuickBooks integration is DISABLED. "
        "Ensure the project-root 'quickbooks/' package is deployed.",
        _qb_import_err,
    )


def is_quickbooks_enabled(tenant):
    if not QUICKBOOKS_AVAILABLE:
        return False
    
    try:
        qb_service = QuickBooksService(tenant)
        integration = qb_service.get_integration()
        
        if not integration or not integration.is_connected:
            return False
            
        if not getattr(settings, 'QUICKBOOKS_AUTO_SYNC_ENABLED', True):
            return False
            
        # Check if token is expired
        if integration.is_token_expired():
            logger.warning(f"QuickBooks token expired for tenant {tenant.id}, disabling auto-sync")
            return False
            
        return True
    except Exception as e:
        logger.warning(f"QuickBooks availability check failed for tenant {tenant.id}: {str(e)}")
        return False


def create_customer_from_student(student):
    # Get validated student data
    student_data = get_student_quickbooks_data(student)
    
    # Validate student has required fields
    if not student_data['is_ready_for_sync']:
        validation_results = student_data['validation_results']
        missing_fields = [k for k, v in validation_results.items() if not v and k.startswith('has_')]
        raise ValidationException(f"Student {student.id} missing required fields: {', '.join(missing_fields)}")
    
    display_name = student_data['display_name']
    display_name_with_id = student_data['display_name_with_id']
    
    primary_email = None
    if student_data['email']:
        primary_email = EmailAddr(Address=student_data['email'])
    
    primary_phone = None
    if student_data['phone']:
        primary_phone = TelephoneNumber(FreeFormNumber=student_data['phone'])
    
    bill_addr = None
    address_parts = [
        student_data['address_line1'],
        student_data['city'],
        student_data['state'],
        student_data['postal_code']
    ]
    if any(part for part in address_parts):
        bill_addr = PhysicalAddr(
            Line1=student_data['address_line1'] or "",
            Line2=student_data['address_line2'] or "",
            City=student_data['city'] or "",
            CountrySubDivisionCode=student_data['state'] or "",
            PostalCode=student_data['postal_code'] or "",
            Country=student_data['country'].name if student_data['country'] else "Zambia"
        )
    
    customer = Customer(
        DisplayName=display_name_with_id,
        GivenName=student_data['first_name'],
        MiddleName=student_data['middle_name'] or None,
        FamilyName=student_data['last_name'],
        CompanyName=None, 
        FullyQualifiedName=display_name_with_id,
        PrintOnCheckName=display_name,
        PrimaryEmailAddr=primary_email,
        PrimaryPhone=primary_phone,
        BillAddr=bill_addr,
        Active=student_data['is_active'],
        Taxable=True,  
        Job=False,
        BillWithParent=False,
        Balance=0.0,  
        BalanceWithJobs=0.0,
        PreferredDeliveryMethod="Print"
    )
    
    return customer


# NOTE: the post_save(Student) auto-customer-creation signal that used to
# live here was removed (2026-07) - it created a QuickBooks customer directly
# from a Student, bypassing QuickBooksFeeSync entirely and duplicating the
# guardian-as-customer sync path. Guardian-as-customer sync now happens
# lazily via QuickBooksFeeSync.sync_guardian_as_customer the first time a
# charge is created for one of the guardian's children (see
# FinanceService._enqueue_qb_sync / core.tasks.sync_fee_charge_to_quickbooks).
# create_customer_from_student/sync_student_to_quickbooks_customer/
# sync_all_students_to_quickbooks below remain in use by the legacy
# `quickbooks_sync` management command (student-centric, admin-triggered
# manual tool) - out of scope for this change.


def sync_student_to_quickbooks_customer(student_id, force=False):
    try:
        student = Student.objects.get(id=student_id)
        tenant = student.tenant
        
        if not force and not is_quickbooks_enabled(tenant):
            return {
                'success': False,
                'message': 'QuickBooks integration is not enabled for this tenant'
            }
        
        qb_service = QuickBooksService(tenant)
        auth_client = qb_service.get_auth_client()
        customer_manager = QuickBooksCustomerManager(auth_client)
        
        customer = create_customer_from_student(student)
        created_customer = customer_manager.create_customer(customer)
        
        return {
            'success': True,
            'message': f'Successfully created QuickBooks customer with ID: {created_customer.Id}',
            'quickbooks_customer_id': created_customer.Id,
            'customer_name': created_customer.DisplayName
        }
        
    except Student.DoesNotExist:
        return {
            'success': False,
            'message': f'Student with ID {student_id} not found'
        }
    except Exception as e:
        logger.error(f"Error syncing student {student_id} to QuickBooks: {str(e)}")
        return {
            'success': False,
            'message': f'Error syncing to QuickBooks: {str(e)}'
        }


def sync_all_students_to_quickbooks(tenant, limit=None):
    if not is_quickbooks_enabled(tenant):
        return {
            'success': False,
            'message': 'QuickBooks integration is not enabled for this tenant'
        }
    
    try:
        students_query = Student.objects.filter(tenant=tenant, is_active=True, is_deleted=False)
        if limit:
            students_query = students_query[:limit]
        
        students = list(students_query)
        total_students = len(students)
        
        if total_students == 0:
            return {
                'success': True,
                'message': 'No students found to sync',
                'total_students': 0,
                'successful_syncs': 0,
                'failed_syncs': 0
            }
        
        qb_service = QuickBooksService(tenant)
        auth_client = qb_service.get_auth_client()
        customer_manager = QuickBooksCustomerManager(auth_client)
        
        successful_syncs = 0
        failed_syncs = 0
        errors = []
        
        for student in students:
            try:
                customer = create_customer_from_student(student)
                created_customer = customer_manager.create_customer(customer)
                successful_syncs += 1
                logger.info(f"Synced student {student.admission_no} to QuickBooks customer {created_customer.Id}")
                
            except Exception as e:
                failed_syncs += 1
                error_msg = f"Failed to sync student {student.admission_no}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return {
            'success': True,
            'message': f'Sync completed: {successful_syncs} successful, {failed_syncs} failed',
            'total_students': total_students,
            'successful_syncs': successful_syncs,
            'failed_syncs': failed_syncs,
            'errors': errors[:10] 
        }
        
    except Exception as e:
        logger.error(f"Error in bulk sync for tenant {tenant.id}: {str(e)}")
        return {
            'success': False,
            'message': f'Bulk sync failed: {str(e)}'
        }


@receiver(post_save, sender=BatchStudent)
def create_student_fees_on_batch_enrollment(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    """
    Signal handler to create fee records when a student is enrolled in a batch
    
    This signal triggers when:
    1. A new BatchStudent record is created (student enrolled in batch)
    2. Creates FinanceFee records based on BatchFeeCategory entries for that batch
    """
    
    # Only process new enrollments, not updates
    if not created:
        return
    
    # Get the tenant (school)
    tenant = instance.tenant
    if not tenant:
        logger.warning(f"BatchStudent {instance.id} has no tenant, skipping fee creation")
        return
    
    student = instance.student
    batch = instance.batch
    
    if not student or not batch:
        logger.warning(f"BatchStudent {instance.id} missing student or batch, skipping fee creation")
        return
    
    logger.info(f"Creating fees for student {student.admission_no} enrolled in batch {batch.name}")

    try:
        from core.services.fee_collection_service import FeeCollectionService
        synced = FeeCollectionService(tenant).sync_student_enrollment(batch, student)
        if synced:
            logger.info(
                f"Synced {synced} fee collection obligation(s) for student "
                f"{student.admission_no} joining batch {batch.name}"
            )
    except Exception as e:
        logger.error(
            f"Failed to sync fee collection obligations for student "
            f"{student.admission_no} in batch {batch.name}: {str(e)}"
        )

    try:
        # Get all fee categories associated with this batch
        batch_fee_categories = BatchFeeCategory.objects.filter(
            batch=batch,
            tenant=tenant
        )

        if not batch_fee_categories.exists():
            logger.info(f"No fee categories found for batch {batch.name}, no fees to create")
            return

        # Use finance service to create fee records
        finance_service = FinanceService(tenant)

        fees_created = 0
        fees_skipped = 0

        for batch_fee_category in batch_fee_categories:
            try:
                # Check if this assignment is scoped to specific students. If
                # scoped (non-empty relation) and the student isn't in it, skip.
                if (batch_fee_category.scoped_students.exists() and
                        not batch_fee_category.scoped_students.filter(student=student).exists()):
                    fees_skipped += 1
                    continue

                # Check if fee already exists (to avoid duplicates)
                existing_fee = FinanceFee.objects.filter(
                    student=student,
                    fee_category=batch_fee_category.fee_category,
                    tenant=tenant
                ).first()

                if existing_fee:
                    logger.info(f"Fee already exists for student {student.admission_no} and category {batch_fee_category.fee_category.name}, skipping")
                    fees_skipped += 1
                    continue

                # NOTE: This block references batch_fee_category.amount, a field
                # removed in migration 0096_remove_batch_fee_category_amount.py.
                # This entire block is currently non-functional (silently fails in
                # the outer except Exception block). Scoping check above is kept
                # logically correct for if/when the pre-existing .amount bug is fixed
                # in a separate ticket. Do not attempt to fix that bug as part of
                # this feature.
                # Create the fee record with the amount from batch fee category
                finance_service.record_student_fee(
                    student_id=str(student.id),
                    fee_category_id=str(batch_fee_category.fee_category.id),
                    balance=batch_fee_category.amount,
                    transaction_date=date.today()
                )

                fees_created += 1
                logger.info(f"Created fee record: {batch_fee_category.fee_category.name} - ${batch_fee_category.amount} for student {student.admission_no}")

            except Exception as e:
                logger.error(f"Failed to create fee record for student {student.admission_no} and category {batch_fee_category.fee_category.name}: {str(e)}")
                continue
        
        # Update student fee payment status
        if fees_created > 0:
            student.has_paid_fees = False  # Student now has outstanding fees
            student.save()
            logger.info(f"Successfully created {fees_created} fee records for student {student.admission_no} (skipped {fees_skipped} existing)")
        else:
            logger.info(f"No new fees created for student {student.admission_no}")
        
    except Exception as e:
        logger.error(f"Unexpected error creating fees for student {student.admission_no} in batch {batch.name}: {str(e)}")


def create_batch_fees_for_student(student_id, batch_id, force=False):
    """
    Utility function to manually create fees for a specific student-batch enrollment
    
    Args:
        student_id: The ID of the student
        batch_id: The ID of the batch  
        force: If True, will create fees even if they already exist
        
    Returns:
        dict: Result information with success status and details
    """
    try:
        # Get the student and batch
        student = Student.objects.get(id=student_id)
        from .models import Batch
        batch = Batch.objects.get(id=batch_id)
        tenant = student.tenant
        
        if not tenant or tenant != batch.tenant:
            return {
                'success': False,
                'message': 'Student and batch must belong to the same tenant'
            }
        
        # Get batch fee categories
        batch_fee_categories = BatchFeeCategory.objects.filter(
            batch=batch,
            tenant=tenant
        )
        
        if not batch_fee_categories.exists():
            return {
                'success': False,
                'message': f'No fee categories configured for batch {batch.name}'
            }
        
        finance_service = FinanceService(tenant)
        fees_created = 0
        fees_skipped = 0
        created_fees = []
        
        for batch_fee_category in batch_fee_categories:
            # Check if this assignment is scoped to specific students. If
            # scoped (non-empty relation) and the student isn't in it, skip.
            if (batch_fee_category.scoped_students.exists() and
                    not batch_fee_category.scoped_students.filter(student=student).exists()):
                fees_skipped += 1
                continue

            # Check if fee already exists
            existing_fee = FinanceFee.objects.filter(
                student=student,
                fee_category=batch_fee_category.fee_category,
                tenant=tenant
            ).first()

            if existing_fee and not force:
                fees_skipped += 1
                continue
            
            if existing_fee and force:
                # Update existing fee balance
                existing_fee.balance = batch_fee_category.amount
                existing_fee.transaction_date = date.today()
                existing_fee.save()
                created_fees.append({
                    'category': batch_fee_category.fee_category.name,
                    'amount': str(batch_fee_category.amount),
                    'action': 'updated'
                })
            else:
                # Create new fee
                finance_service.record_student_fee(
                    student_id=str(student.id),
                    fee_category_id=str(batch_fee_category.fee_category.id),
                    balance=batch_fee_category.amount,
                    transaction_date=date.today()
                )
                created_fees.append({
                    'category': batch_fee_category.fee_category.name,
                    'amount': str(batch_fee_category.amount),
                    'action': 'created'
                })
                fees_created += 1
        
        # Update student fee status
        if fees_created > 0:
            student.has_paid_fees = False
            student.save()
        
        return {
            'success': True,
            'message': f'Processed {fees_created} fees for student {student.admission_no} in batch {batch.name}',
            'fees_created': fees_created,
            'fees_skipped': fees_skipped,
            'fees': created_fees
        }
        
    except Student.DoesNotExist:
        return {
            'success': False,
            'message': f'Student with ID {student_id} not found'
        }
    except Exception as e:
        logger.error(f"Error creating batch fees for student {student_id} in batch {batch_id}: {str(e)}")
        return {
            'success': False,
            'message': f'Error creating fees: {str(e)}'
        }


def sync_all_batch_fees_for_tenant(tenant, limit=None):
    """
    Utility function to sync all batch enrollments to create missing fee records
    
    Args:
        tenant: The tenant (school) to sync
        limit: Optional limit on number of enrollments to process
        
    Returns:
        dict: Summary of sync results
    """
    try:
        # Get all active batch student enrollments
        enrollments_query = BatchStudent.objects.filter(
            tenant=tenant, 
            is_active=True,
            student__is_active=True,
            student__is_deleted=False
        ).select_related('student', 'batch')
        
        if limit:
            enrollments_query = enrollments_query[:limit]
        
        enrollments = list(enrollments_query)
        total_enrollments = len(enrollments)
        
        if total_enrollments == 0:
            return {
                'success': True,
                'message': 'No active enrollments found to sync',
                'total_enrollments': 0,
                'fees_created': 0,
                'enrollments_processed': 0
            }
        
        fees_created = 0
        enrollments_processed = 0
        errors = []
        
        for enrollment in enrollments:
            try:
                result = create_batch_fees_for_student(
                    str(enrollment.student.id),
                    str(enrollment.batch.id),
                    force=False
                )
                
                if result['success']:
                    fees_created += result.get('fees_created', 0)
                    enrollments_processed += 1
                else:
                    error_msg = f"Failed for {enrollment.student.admission_no} in {enrollment.batch.name}: {result['message']}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                
            except Exception as e:
                error_msg = f"Error processing enrollment {enrollment.id}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return {
            'success': True,
            'message': f'Sync completed: {fees_created} fees created for {enrollments_processed} enrollments',
            'total_enrollments': total_enrollments,
            'fees_created': fees_created,
            'enrollments_processed': enrollments_processed,
            'errors': errors[:10]  # Limit errors in response
        }
        
    except Exception as e:
        logger.error(f"Error in bulk fee sync for tenant {tenant.id}: {str(e)}")
        return {
            'success': False,
            'message': f'Bulk fee sync failed: {str(e)}'
        }