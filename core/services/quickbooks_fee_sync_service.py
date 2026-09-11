import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum
from django.conf import settings

from core.services.base import TenantAwareService
from core.services.exceptions import ValidationException, NotFoundException, BusinessLogicException
from core.models import (
    Student, Guardian, FeeCategory, FeeParticular, AcademicYear, FeeTransaction,
    FamilyInvoice, FamilyInvoiceLine,
    QuickBooksCustomerSync, QuickBooksFeeInvoiceSync, QuickBooksFeeInvoiceLineSync,
    QuickBooksFeePaymentSync, QuickBooksSyncLog, QuickBooksConfiguration,
    CurrencyConfiguration
)
from core.services.quickbooks_service import QuickBooksService
from core.utils.model_field_validator import get_guardian_quickbooks_data, validate_guardian_fields_for_quickbooks

logger = logging.getLogger(__name__)

try:
    from quickbooks.accounts import (
        QuickBooksCustomerManager, QuickBooksInvoiceManager,
        Customer, EmailAddr, PhysicalAddr, TelephoneNumber,
        Invoice, Line, CustomerRef, CurrencyRef, Payment,
        create_fee_invoice, create_fee_payment
    )
except ImportError:
    logger.warning("QuickBooks integration not available - missing dependencies")
    QuickBooksCustomerManager = None
    QuickBooksInvoiceManager = None


class QuickBooksFeeSync:
    """Service for synchronizing fee collection with QuickBooks"""
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.quickbooks_service = QuickBooksService(tenant)
        self._customer_manager = None
        self._invoice_manager = None
        self._config = None
    
    @property
    def customer_manager(self) -> 'QuickBooksCustomerManager':
        """Get QuickBooks customer manager (lazy loading)"""
        if not self._customer_manager and QuickBooksCustomerManager:
            try:
                auth = self.quickbooks_service.get_auth_client()
                # Check if authentication is valid
                auth.ensure_valid_token()
                self._customer_manager = QuickBooksCustomerManager(auth)
            except ValueError as e:
                if "No access token available" in str(e):
                    raise BusinessLogicException("QuickBooks authentication required. Please reconnect to QuickBooks.")
                raise BusinessLogicException(f"QuickBooks authentication error: {str(e)}")
            except Exception as e:
                if "expired" in str(e).lower() or "invalid" in str(e).lower():
                    raise BusinessLogicException("QuickBooks authentication expired. Please reconnect to QuickBooks.")
                raise BusinessLogicException(f"QuickBooks authentication failed: {str(e)}")
        return self._customer_manager
    
    @property
    def invoice_manager(self) -> 'QuickBooksInvoiceManager':
        """Get QuickBooks invoice manager (lazy loading)"""
        if not self._invoice_manager and QuickBooksInvoiceManager:
            try:
                auth = self.quickbooks_service.get_auth_client()
                # Check if authentication is valid
                auth.ensure_valid_token()
                self._invoice_manager = QuickBooksInvoiceManager(auth)
            except ValueError as e:
                if "No access token available" in str(e):
                    raise BusinessLogicException("QuickBooks authentication required. Please reconnect to QuickBooks.")
                raise BusinessLogicException(f"QuickBooks authentication error: {str(e)}")
            except Exception as e:
                if "expired" in str(e).lower() or "invalid" in str(e).lower():
                    raise BusinessLogicException("QuickBooks authentication expired. Please reconnect to QuickBooks.")
                raise BusinessLogicException(f"QuickBooks authentication failed: {str(e)}")
        return self._invoice_manager
    
    @property
    def config(self) -> QuickBooksConfiguration:
        """Get or create QuickBooks configuration"""
        if not self._config:
            self._config, created = QuickBooksConfiguration.objects.get_or_create(
                tenant=self.tenant,
                defaults={
                    'auto_sync_customers': True,
                    'auto_sync_invoices': True,
                    'auto_sync_payments': True,
                    'invoice_prefix': 'FEE',
                    'payment_terms_days': 30,
                    'send_receipts_by_email': True
                }
            )
        return self._config
    
    def _service_item_ref(self) -> Dict[str, str]:
        """The QuickBooks ``ItemRef`` every fee line is booked against.

        Uses ``QuickBooksConfiguration.default_service_item`` (a QuickBooks
        Item Id) when set; otherwise falls back to id ``"1"`` and logs a
        warning, since a fresh production company rarely has a usable item 1.
        """
        item_id = (self.config.default_service_item or '').strip()
        if item_id:
            return {'value': item_id, 'name': 'Services'}
        logger.warning(
            "QuickBooksConfiguration.default_service_item is not set for tenant "
            "%s; falling back to Item id '1'. Fee charges may post to the wrong "
            "income account.", self.tenant.id,
        )
        return {'value': '1', 'name': 'Services'}

    def list_service_items(self) -> List[Dict[str, Any]]:
        """Return the tenant's QuickBooks Service / NonInventory items as
        ``[{'id', 'name', 'type', 'income_account'}]`` for the settings picker.
        """
        raw = self.invoice_manager.get_items()
        items = []
        for it in raw:
            income = (it.get('IncomeAccountRef') or {})
            items.append({
                'id': it.get('Id'),
                'name': it.get('Name') or it.get('FullyQualifiedName'),
                'type': it.get('Type'),
                'income_account': income.get('name'),
            })
        return items

    def validate_service_item(self, item_id: str) -> bool:
        """True if ``item_id`` is a real Service/NonInventory item in QuickBooks."""
        if not item_id:
            return False
        return any(str(i['id']) == str(item_id) for i in self.list_service_items())

    def _log_sync(self, sync_type: str, action_type: str, status: str,
                  object_type: str = None, object_id: str = None, 
                  quickbooks_id: str = None, details: dict = None, 
                  error_message: str = None, duration: float = None):
        """Log synchronization activity"""
        try:
            QuickBooksSyncLog.objects.create(
                tenant=self.tenant,
                sync_type=sync_type,
                action_type=action_type,
                status=status,
                object_type=object_type or '',
                object_id=object_id,
                quickbooks_id=quickbooks_id,
                details=details or {},
                error_message=error_message,
                duration_seconds=duration
            )
        except Exception as e:
            logger.error(f"Failed to log sync activity: {str(e)}")
    
    def sync_guardian_as_customer(self, guardian: Guardian, force_update: bool = False) -> QuickBooksCustomerSync:
        """Sync a guardian (parent) as a QuickBooks customer.

        The guardian - not the student - is the QuickBooks customer: all of a
        guardian's children share this one customer record, so a family with
        multiple students gets one consolidated invoice, not one per child.
        """
        start_time = timezone.now()

        try:
            if not validate_guardian_fields_for_quickbooks(guardian):
                validation_results = get_guardian_quickbooks_data(guardian)['validation_results']
                missing_fields = [k for k, v in validation_results.items() if not v and k.startswith('has_')]
                raise ValidationException(f"Guardian {guardian.id} missing required fields for QuickBooks sync: {', '.join(missing_fields)}")

            guardian_data = get_guardian_quickbooks_data(guardian)

            try:
                customer_sync = QuickBooksCustomerSync.objects.get(
                    tenant=self.tenant,
                    guardian=guardian
                )
                created = False
            except QuickBooksCustomerSync.DoesNotExist:
                customer_sync = QuickBooksCustomerSync.objects.create(
                    tenant=self.tenant,
                    guardian=guardian,
                    customer_display_name=guardian_data['display_name_with_id'],
                    sync_status='pending',
                    quickbooks_customer_id=None
                )
                created = True

            # Skip if already synced and not forcing update
            if not created and customer_sync.sync_status == 'synced' and not force_update:
                return customer_sync

            # Guardians have no admission_no, so the display name is suffixed
            # with a short guardian id to guarantee uniqueness in QuickBooks.
            display_name = guardian_data['display_name_with_id']

            customer_data = {
                'DisplayName': display_name,
                'GivenName': guardian_data['first_name'],
                'FamilyName': guardian_data['last_name'],
                'CompanyName': self.tenant.name,
            }

            if guardian_data['email']:
                customer_data['PrimaryEmailAddr'] = EmailAddr(Address=guardian_data['email'])

            if guardian_data['phone']:
                customer_data['PrimaryPhone'] = TelephoneNumber(FreeFormNumber=guardian_data['phone'])

            address_parts = [
                guardian_data['address_line1'],
                guardian_data['city'],
                guardian_data['state'],
            ]
            if any(part for part in address_parts):
                customer_data['BillAddr'] = PhysicalAddr(
                    Line1=guardian_data['address_line1'] or '',
                    Line2=guardian_data['address_line2'] or '',
                    City=guardian_data['city'] or '',
                    CountrySubDivisionCode=guardian_data['state'] or '',
                    PostalCode=guardian_data['postal_code'] or '',
                    Country=guardian_data['country'].name if guardian_data['country'] else 'Zambia'
                )

            customer = Customer(**customer_data)

            # Create or update in QuickBooks
            if customer_sync.quickbooks_customer_id:
                customer.Id = customer_sync.quickbooks_customer_id
                updated_customer = self.customer_manager.update_customer(customer)
                quickbooks_id = updated_customer.Id
            else:
                # Duplicate guard: a local sync record may be missing even though the
                # customer already exists in QuickBooks (e.g. re-deployed DB). Search by
                # the unique DisplayName (includes the guardian id) and link instead of
                # creating a duplicate.
                existing_id = None
                try:
                    matches = self.customer_manager.search_customers(display_name, max_results=5)
                    for m in matches:
                        if getattr(m, 'DisplayName', None) == display_name:
                            existing_id = m.Id
                            break
                except Exception as search_err:
                    logger.warning(f"QB duplicate-check failed for {display_name}: {search_err}")

                if existing_id:
                    customer.Id = existing_id
                    updated_customer = self.customer_manager.update_customer(customer)
                    quickbooks_id = updated_customer.Id
                    logger.info(f"Linked to existing QuickBooks customer {quickbooks_id} for {display_name}")
                else:
                    created_customer = self.customer_manager.create_customer(customer)
                    quickbooks_id = created_customer.Id

            customer_sync.quickbooks_customer_id = quickbooks_id
            customer_sync.customer_display_name = display_name
            customer_sync.sync_status = 'synced'
            customer_sync.last_synced = timezone.now()
            customer_sync.sync_error = None
            customer_sync.save()

            duration = (timezone.now() - start_time).total_seconds()
            self._log_sync(
                'customer', 'sync', 'success',
                'Guardian', str(guardian.id), quickbooks_id,
                {'display_name': display_name, 'intuit_tid': self.customer_manager.last_intuit_tid},
                None, duration
            )

            return customer_sync

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to sync guardian {guardian.id} as customer: {error_msg}")

            if 'customer_sync' in locals():
                customer_sync.sync_status = 'failed'
                customer_sync.sync_error = error_msg
                customer_sync.save()

            duration = (timezone.now() - start_time).total_seconds()
            safe_display_name = f"{guardian.first_name} {guardian.last_name}" if hasattr(guardian, 'first_name') else 'Unknown'

            self._log_sync(
                'customer', 'sync', 'failed',
                'Guardian', str(guardian.id), None,
                {'display_name': safe_display_name}, error_msg, duration
            )

            raise BusinessLogicException(f"Failed to sync guardian as customer: {error_msg}")

    def sync_student_as_customer(self, student: Student, force_update: bool = False) -> Optional[QuickBooksCustomerSync]:
        """Backward-compatible thin wrapper: resolves the student's billing
        guardian (immediate_contact) and syncs that guardian as the customer.
        Returns None if the student has no billing guardian set.
        """
        guardian = student.immediate_contact
        if guardian is None:
            logger.warning(f"Student {student.id} has no immediate_contact guardian; cannot sync a QuickBooks customer")
            return None
        return self.sync_guardian_as_customer(guardian, force_update=force_update)
    
    def upsert_family_invoice_sync(self, family_invoice_line: FamilyInvoiceLine) -> QuickBooksFeeInvoiceLineSync:
        """Mirror one local FamilyInvoiceLine (a single student's charge) into
        the guardian's consolidated QuickBooks invoice.

        Get-or-creates the guardian-level QuickBooksFeeInvoiceSync header for
        (guardian, academic_year) - only the family's FIRST charge for a year
        creates a new QB invoice; every subsequent charge (same or different
        child) appends/updates a line on that same invoice via a sparse
        update, so a family with N children ends up with exactly one
        consolidated QB invoice per year, not one per child. The line itself
        is tracked by QuickBooksFeeInvoiceLineSync, keyed on finance_fee
        (idempotency guard).
        """
        start_time = timezone.now()
        family_invoice = family_invoice_line.invoice
        guardian = family_invoice.guardian
        academic_year = family_invoice.academic_year
        student = family_invoice_line.student

        # Idempotency: this charge's line already synced.
        existing_line = QuickBooksFeeInvoiceLineSync.objects.filter(
            tenant=self.tenant, finance_fee=family_invoice_line.finance_fee,
        ).first()
        if existing_line is not None and existing_line.sync_status == 'synced':
            return existing_line

        try:
            customer_sync = self.sync_guardian_as_customer(guardian)

            due_date = timezone.now().date() + timedelta(days=self.config.payment_terms_days)

            with transaction.atomic():
                invoice_sync, invoice_sync_created = QuickBooksFeeInvoiceSync.objects.get_or_create(
                    tenant=self.tenant, guardian=guardian, academic_year=academic_year,
                    defaults={
                        'family_invoice': family_invoice,
                        'quickbooks_customer_sync': customer_sync,
                        'total_amount': family_invoice_line.amount,
                        'due_date': due_date,
                        'balance_remaining': family_invoice_line.amount,
                        'sync_status': 'draft',
                    },
                )
                if invoice_sync.family_invoice_id is None:
                    invoice_sync.family_invoice = family_invoice
                    invoice_sync.save(update_fields=['family_invoice'])

                line_sync, line_created = QuickBooksFeeInvoiceLineSync.objects.get_or_create(
                    tenant=self.tenant, finance_fee=family_invoice_line.finance_fee,
                    defaults={
                        'invoice_sync': invoice_sync,
                        'student': student,
                        'description': f"{student.first_name} {student.last_name} - {family_invoice_line.description}",
                        'amount': family_invoice_line.amount,
                        'sync_status': 'draft',
                    },
                )

            if line_sync.sync_status == 'synced':
                return line_sync

            item_ref = self._service_item_ref()
            currency = CurrencyConfiguration.get_active_currency(self.tenant)
            currency_code = currency.currency_code
            currency_ref = None
            if currency_code and currency_code != 'USD':
                currency_ref = {'value': currency_code, 'name': currency_code}
            custom_fields = [
                {"DefinitionId": "2", "Name": "AcademicYear", "StringValue": academic_year.name if academic_year else ""},
            ]

            # Serialise the QuickBooks call for this (guardian, year) header so
            # two concurrent first-charges can't each create a QB invoice.
            with transaction.atomic():
                invoice_sync = (
                    QuickBooksFeeInvoiceSync.objects
                    .select_for_update()
                    .get(pk=invoice_sync.pk)
                )

                # Our own line syncs on this header, oldest first (deterministic
                # order for the back-mapping below).
                our_line_syncs = list(
                    invoice_sync.lines.all().order_by('created_at')
                )
                our_known_ids = {ls.qb_line_id for ls in our_line_syncs if ls.qb_line_id}

                def _our_line_payload(ls, line_num):
                    return Line(
                        Id=ls.qb_line_id or None,
                        LineNum=line_num,
                        Amount=float(ls.amount),
                        Description=ls.description,
                        DetailType='SalesItemLineDetail',
                        SalesItemLineDetail={
                            'ItemRef': item_ref,
                            'UnitPrice': float(ls.amount),
                            'Qty': 1,
                        },
                    ).dict(exclude_none=True)

                total_amount = sum(
                    (Decimal(str(ls.amount)) for ls in our_line_syncs), Decimal('0')
                )

                if invoice_sync.quickbooks_invoice_id:
                    current = self.invoice_manager.get_invoice(invoice_sync.quickbooks_invoice_id)
                    current_lines = list(getattr(current, 'Line', None) or [])
                    # Lines on the QB invoice that Pinewood did not put there
                    # (the school's own history on a reconciliation-linked
                    # invoice). Keep them verbatim - never rebuild them away.
                    foreign_lines = [
                        cl for cl in current_lines
                        if isinstance(cl, dict) and cl.get('Id')
                        and cl.get('Id') not in our_known_ids
                        and cl.get('DetailType') == 'SalesItemLineDetail'
                    ]
                    foreign_ids = {cl['Id'] for cl in foreign_lines}

                    qb_lines = list(foreign_lines)
                    for i, ls in enumerate(our_line_syncs, len(foreign_lines) + 1):
                        qb_lines.append(_our_line_payload(ls, i))

                    qb_invoice = Invoice(
                        Id=invoice_sync.quickbooks_invoice_id,
                        SyncToken=current.SyncToken if current else '0',
                        sparse=True,
                        CustomerRef=CustomerRef(
                            value=customer_sync.quickbooks_customer_id,
                            name=customer_sync.customer_display_name,
                        ),
                        Line=qb_lines,
                        CurrencyRef=currency_ref,
                        CustomField=custom_fields,
                    )
                    saved_invoice = self.invoice_manager.update_invoice(qb_invoice)
                else:
                    foreign_ids = set()
                    qb_invoice = create_fee_invoice(
                        customer_id=customer_sync.quickbooks_customer_id,
                        customer_name=customer_sync.customer_display_name,
                        fee_items=[
                            {'name': ls.description, 'description': ls.description,
                             'amount': float(ls.amount)}
                            for ls in our_line_syncs
                        ],
                        currency_code=currency_code,
                        due_date=due_date.strftime('%Y-%m-%d'),
                        item_ref=item_ref,
                    )
                    qb_invoice.CustomField = custom_fields
                    saved_invoice = self.invoice_manager.create_invoice(qb_invoice)

                # Map QB line ids back onto our line syncs (ignoring any
                # preserved foreign lines).
                our_saved = [
                    sl for sl in (saved_invoice.Line or [])
                    if isinstance(sl, dict)
                    and sl.get('DetailType') == 'SalesItemLineDetail'
                    and sl.get('Id') not in foreign_ids
                ]
                for line_obj, saved_line in zip(our_line_syncs, our_saved):
                    qb_line_id = saved_line.get('Id')
                    if qb_line_id:
                        QuickBooksFeeInvoiceLineSync.objects.filter(pk=line_obj.pk).update(
                            qb_line_id=qb_line_id, sync_status='synced',
                            synced_at=timezone.now(),
                        )

                invoice_sync.quickbooks_invoice_id = saved_invoice.Id
                invoice_sync.quickbooks_doc_number = saved_invoice.DocNumber
                invoice_sync.sync_status = 'synced'
                invoice_sync.synced_at = timezone.now()
                invoice_sync.total_amount = total_amount
                invoice_sync.balance_remaining = Decimal(str(
                    saved_invoice.Balance if saved_invoice.Balance is not None else total_amount
                ))
                invoice_sync.save()

            line_sync.refresh_from_db()

            duration = (timezone.now() - start_time).total_seconds()
            self._log_sync(
                'invoice', 'update' if not invoice_sync_created else 'create', 'success',
                'QuickBooksFeeInvoiceSync', str(invoice_sync.id), saved_invoice.Id,
                {
                    'guardian_id': str(guardian.id), 'student_id': str(student.id),
                    'total_amount': float(total_amount),
                    'intuit_tid': self.invoice_manager.last_intuit_tid,
                },
                None, duration,
            )

            return line_sync

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to upsert family invoice for guardian {guardian.id} (student {student.id}): {error_msg}")

            if 'line_sync' in locals():
                line_sync.sync_status = 'failed'
                line_sync.sync_error = error_msg
                line_sync.save()
            if 'invoice_sync' in locals():
                invoice_sync.sync_status = 'failed'
                invoice_sync.sync_error = error_msg
                invoice_sync.save()

            duration = (timezone.now() - start_time).total_seconds()
            self._log_sync(
                'invoice', 'sync', 'failed',
                'Guardian', str(guardian.id), None,
                {'student_id': str(student.id)}, error_msg, duration,
            )

            raise BusinessLogicException(f"Failed to sync family invoice: {error_msg}")
    
    def create_fee_payment_sync(self, student: Student, amount: Decimal,
                               payment_date: datetime = None,
                               payment_method: str = None,
                               reference_number: str = None,
                               related_invoice: QuickBooksFeeInvoiceSync = None,
                               notes: str = None,
                               fee_transaction=None) -> QuickBooksFeePaymentSync:
        """Create and sync a fee payment to QuickBooks.

        ``fee_transaction`` links back to the local payment ledger row and is the
        idempotency key: a payment already synced for that row is returned as-is.
        When ``related_invoice`` is not supplied it is auto-resolved from the
        same student + fee category + academic year as the ledger row, so the QB
        payment is applied to the correct year's invoice.
        """
        start_time = timezone.now()

        # Idempotency: never sync the same local payment twice.
        if fee_transaction is not None:
            existing = QuickBooksFeePaymentSync.objects.filter(
                tenant=self.tenant, fee_transaction=fee_transaction,
            ).first()
            if existing is not None:
                return existing

        # Auto-resolve the guardian's consolidated invoice via the local
        # FamilyInvoiceLine for this charge, when not provided.
        if related_invoice is None and fee_transaction is not None:
            guardian = student.immediate_contact
            if guardian is not None:
                related_invoice = QuickBooksFeeInvoiceSync.objects.filter(
                    tenant=self.tenant, guardian=guardian,
                    academic_year_id=fee_transaction.academic_year_id,
                ).order_by('-synced_at').first()

        try:
            # Ensure the student's billing guardian is synced as customer
            customer_sync = self.sync_student_as_customer(student)

            # Set default payment date
            if not payment_date:
                payment_date = timezone.now().date()

            # Create payment sync record
            with transaction.atomic():
                payment_sync = QuickBooksFeePaymentSync.objects.create(
                    tenant=self.tenant,
                    student=student,
                    related_invoice=related_invoice,
                    fee_transaction=fee_transaction,
                    quickbooks_customer_sync=customer_sync,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    reference_number=reference_number,
                    notes=notes,
                    sync_status='pending'
                )

                # Generate receipt number
                payment_sync.generate_receipt_number()

            # Get currency
            currency = CurrencyConfiguration.get_active_currency(self.tenant)
            currency_code = currency.currency_code
            
            # Create QuickBooks payment
            qb_payment = create_fee_payment(
                customer_id=customer_sync.quickbooks_customer_id,
                customer_name=customer_sync.customer_display_name,
                amount=float(amount),
                invoice_id=related_invoice.quickbooks_invoice_id if related_invoice else None,
                payment_method=payment_method,
                reference_number=payment_sync.receipt_number,
                currency_code=currency_code
            )
            
            # Add private note
            if notes:
                qb_payment.PrivateNote = notes
            
            # Create payment in QuickBooks
            created_payment = self.invoice_manager.create_payment(qb_payment)
            
            # Update sync record
            payment_sync.quickbooks_payment_id = created_payment.Id
            payment_sync.sync_status = 'synced'
            payment_sync.synced_at = timezone.now()
            payment_sync.receipt_generated = True
            if related_invoice is None:
                # Applied to no invoice - it lands in QuickBooks as an
                # unapplied credit. Flag it so quickbooks_reconcile can relink
                # it once the invoice sync exists.
                payment_sync.needs_review = True
                payment_sync.review_note = (
                    'QuickBooks payment created without a linked invoice '
                    '(unapplied credit); relink when the invoice is synced'
                )
            payment_sync.save()

            # Update related invoice balance if applicable
            if related_invoice:
                related_invoice.balance_remaining = max(
                    Decimal('0'),
                    related_invoice.balance_remaining - amount
                )
                related_invoice.is_paid = related_invoice.balance_remaining == Decimal('0')
                related_invoice.save()
            
            # Log success
            duration = (timezone.now() - start_time).total_seconds()
            self._log_sync(
                'payment', 'create', 'success',
                'QuickBooksFeePaymentSync', str(payment_sync.id), created_payment.Id,
                {
                    'receipt_number': payment_sync.receipt_number,
                    'amount': float(amount),
                    'payment_method': payment_method,
                    'intuit_tid': self.invoice_manager.last_intuit_tid,
                }, None, duration
            )
            
            return payment_sync
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to create fee payment for student {student.id}: {error_msg}")
            
            # Update sync record with error
            if 'payment_sync' in locals():
                payment_sync.sync_status = 'failed'
                payment_sync.sync_error = error_msg
                payment_sync.save()
            
            # Log failure
            duration = (timezone.now() - start_time).total_seconds()
            self._log_sync(
                'payment', 'create', 'failed',
                'Student', str(student.id), None,
                {'amount': float(amount)}, error_msg, duration
            )
            
            raise BusinessLogicException(f"Failed to create fee payment: {error_msg}")
    
    def bulk_sync_students_as_customers(self, students: List[Student] = None) -> Dict[str, Any]:
        """Bulk sync students as QuickBooks customers"""
        start_time = timezone.now()
        
        if not students:
            students = Student.objects.filter(tenant=self.tenant, is_active=True)
        
        results = {
            'total': len(students),
            'synced': 0,
            'failed': 0,
            'errors': []
        }
        
        for student in students:
            try:
                self.sync_student_as_customer(student)
                results['synced'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'student_id': str(student.id),
                    'student_name': f"{student.first_name} {student.last_name}",
                    'error': str(e)
                })
                logger.error(f"Failed to sync student {student.id}: {str(e)}")
        
        # Log bulk sync results
        duration = (timezone.now() - start_time).total_seconds()
        status = 'success' if results['failed'] == 0 else ('partial' if results['synced'] > 0 else 'failed')
        
        self._log_sync(
            'bulk_sync', 'sync', status,
            'Student', None, None, results, None, duration
        )
        
        return results
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get overall sync status and statistics"""
        return {
            'quickbooks_connected': self.quickbooks_service.get_connection_status()['connected'],
            'auto_sync_enabled': {
                'customers': self.config.auto_sync_customers,
                'invoices': self.config.auto_sync_invoices,
                'payments': self.config.auto_sync_payments
            },
            'sync_stats': {
                'customers_synced': QuickBooksCustomerSync.objects.filter(
                    tenant=self.tenant, sync_status='synced'
                ).count(),
                'customers_pending': QuickBooksCustomerSync.objects.filter(
                    tenant=self.tenant, sync_status='pending'
                ).count(),
                'customers_failed': QuickBooksCustomerSync.objects.filter(
                    tenant=self.tenant, sync_status='failed'
                ).count(),
                'invoices_synced': QuickBooksFeeInvoiceSync.objects.filter(
                    tenant=self.tenant, sync_status='synced'
                ).count(),
                'payments_synced': QuickBooksFeePaymentSync.objects.filter(
                    tenant=self.tenant, sync_status='synced'
                ).count()
            },
            'last_reconciliation': self.config.last_reconciliation_date,
            'config': {
                'invoice_prefix': self.config.invoice_prefix,
                'payment_terms_days': self.config.payment_terms_days,
                'send_receipts_by_email': self.config.send_receipts_by_email
            }
        }
    
    def reconcile_payments(self, start_date: datetime = None, end_date: datetime = None,
                           academic_year=None) -> Dict[str, Any]:
        """Reconcile local payment ledger against QuickBooks, optionally scoped to
        an academic year.

        Reads back QB sync state to flag mismatches: local payments that never
        synced, and synced payments whose QB payment id has gone missing (e.g.
        voided in QuickBooks). Pinewood remains the source of truth.
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()

        payments = QuickBooksFeePaymentSync.objects.filter(
            tenant=self.tenant,
            payment_date__gte=start_date.date(),
            payment_date__lte=end_date.date(),
        )
        if academic_year is not None:
            # Scope via the local ledger row's academic year.
            payments = payments.filter(fee_transaction__academic_year=academic_year)

        discrepancies = []
        synced_total = Decimal('0')
        for p in payments.select_related('fee_transaction'):
            if p.sync_status == 'synced':
                synced_total += p.amount
                if not p.quickbooks_payment_id:
                    discrepancies.append({
                        'payment_sync_id': str(p.id), 'issue': 'synced_without_qb_id',
                        'amount': str(p.amount),
                    })
            elif p.sync_status in ('pending', 'failed'):
                discrepancies.append({
                    'payment_sync_id': str(p.id), 'issue': f'not_synced ({p.sync_status})',
                    'amount': str(p.amount),
                    'fee_transaction_id': str(p.fee_transaction_id) if p.fee_transaction_id else None,
                })

        # Local payment ledger rows in scope that have NO QB sync record at all.
        local_pay_q = Q(tenant=self.tenant, transaction_type='payment',
                        transaction_date__gte=start_date, transaction_date__lte=end_date)
        if academic_year is not None:
            local_pay_q &= Q(academic_year=academic_year)
        unsynced = FeeTransaction.objects.filter(local_pay_q, qb_payment_syncs__isnull=True)
        for ft in unsynced:
            discrepancies.append({
                'fee_transaction_id': str(ft.id), 'issue': 'no_qb_sync_record',
                'amount': str(ft.amount),
            })

        reconciliation_results = {
            'period': f"{start_date.date()} to {end_date.date()}",
            'academic_year': academic_year.name if academic_year else None,
            'synced_payments_total': synced_total,
            'discrepancy_count': len(discrepancies),
            'discrepancies': discrepancies,
            'summary': 'Reconciliation completed' if not discrepancies else 'Discrepancies found',
        }

        # Update reconciliation date
        self.config.last_reconciliation_date = timezone.now()
        self.config.save()

        return reconciliation_results

    def reconcile_invoices(self, academic_year=None,
                           tolerance: Decimal = Decimal('0.01')) -> Dict[str, Any]:
        """Compare local FamilyInvoice balances against their QuickBooks mirror.

        For every FamilyInvoice in scope, checks that three numbers agree: the
        local ``balance_due``, the cached ``QuickBooksFeeInvoiceSync.balance_remaining``,
        and the live ``Invoice.Balance`` in QuickBooks. Flags invoices that
        never linked/synced, balance mismatches, sync rows whose QuickBooks
        invoice has gone missing, and sync rows linked to no local invoice.
        Read-only - Pinewood stays the source of truth.
        """
        invoices = FamilyInvoice.objects.filter(tenant=self.tenant).select_related(
            'guardian', 'academic_year',
        )
        if academic_year is not None:
            invoices = invoices.filter(academic_year=academic_year)

        discrepancies = []
        checked = 0
        local_balance_total = Decimal('0')

        for fi in invoices:
            checked += 1
            local_balance_total += fi.balance_due or Decimal('0')
            sync = QuickBooksFeeInvoiceSync.objects.filter(
                tenant=self.tenant, family_invoice=fi,
            ).first()

            if sync is None or sync.sync_status != 'synced' or not sync.quickbooks_invoice_id:
                discrepancies.append({
                    'family_invoice_id': str(fi.id),
                    'invoice_number': fi.invoice_number,
                    'issue': 'not_synced' if sync is None else f'not_synced ({sync.sync_status})',
                    'local_balance_due': str(fi.balance_due),
                })
                continue

            try:
                qb_invoice = self.invoice_manager.get_invoice(sync.quickbooks_invoice_id)
            except Exception as e:
                discrepancies.append({
                    'family_invoice_id': str(fi.id),
                    'invoice_number': fi.invoice_number,
                    'quickbooks_invoice_id': sync.quickbooks_invoice_id,
                    'issue': 'qb_lookup_failed',
                    'error': str(e),
                })
                continue

            if qb_invoice is None:
                discrepancies.append({
                    'family_invoice_id': str(fi.id),
                    'invoice_number': fi.invoice_number,
                    'quickbooks_invoice_id': sync.quickbooks_invoice_id,
                    'issue': 'missing_in_qbo',
                    'local_balance_due': str(fi.balance_due),
                })
                continue

            local_balance = fi.balance_due or Decimal('0')
            cached_balance = sync.balance_remaining or Decimal('0')
            live_balance = Decimal(str(qb_invoice.Balance if qb_invoice.Balance is not None else '0'))

            if (abs(local_balance - live_balance) > tolerance
                    or abs(local_balance - cached_balance) > tolerance):
                discrepancies.append({
                    'family_invoice_id': str(fi.id),
                    'invoice_number': fi.invoice_number,
                    'quickbooks_invoice_id': sync.quickbooks_invoice_id,
                    'issue': 'balance_mismatch',
                    'local_balance_due': str(local_balance),
                    'cached_balance_remaining': str(cached_balance),
                    'qbo_balance': str(live_balance),
                })

        # Sync rows that point at nothing local (orphaned links).
        orphan_syncs = QuickBooksFeeInvoiceSync.objects.filter(
            tenant=self.tenant, family_invoice__isnull=True,
        ).exclude(quickbooks_invoice_id__isnull=True).exclude(quickbooks_invoice_id='')
        if academic_year is not None:
            orphan_syncs = orphan_syncs.filter(academic_year=academic_year)
        for s in orphan_syncs:
            discrepancies.append({
                'invoice_sync_id': str(s.id),
                'quickbooks_invoice_id': s.quickbooks_invoice_id,
                'issue': 'orphan_sync_no_local_invoice',
            })

        results = {
            'academic_year': academic_year.name if academic_year else None,
            'invoices_checked': checked,
            'local_balance_due_total': local_balance_total,
            'discrepancy_count': len(discrepancies),
            'discrepancies': discrepancies,
            'summary': 'Reconciliation completed' if not discrepancies else 'Discrepancies found',
        }

        self.config.last_reconciliation_date = timezone.now()
        self.config.save()

        return results

    def relink_unapplied_payments(self, academic_year=None) -> Dict[str, Any]:
        """Attach a QuickBooks invoice to payments that synced as an unapplied
        credit (``needs_review`` + no ``related_invoice``) now that the
        invoice sync exists. Pushes the ``LinkedTxn`` to QuickBooks and updates
        the local invoice balance.
        """
        qs = QuickBooksFeePaymentSync.objects.filter(
            tenant=self.tenant, sync_status='synced', needs_review=True,
            related_invoice__isnull=True,
        ).exclude(quickbooks_payment_id__isnull=True).exclude(quickbooks_payment_id='') \
         .select_related('student', 'student__immediate_contact', 'fee_transaction')

        relinked, skipped, errors = 0, 0, []
        for ps in qs:
            guardian = getattr(ps.student, 'immediate_contact', None) if ps.student else None
            ay_id = ps.fee_transaction.academic_year_id if ps.fee_transaction else None
            if academic_year is not None and ay_id != academic_year.id:
                continue
            if guardian is None or ay_id is None:
                skipped += 1
                continue

            invoice_sync = QuickBooksFeeInvoiceSync.objects.filter(
                tenant=self.tenant, guardian=guardian, academic_year_id=ay_id,
                sync_status='synced',
            ).exclude(quickbooks_invoice_id__isnull=True).exclude(quickbooks_invoice_id='').first()
            if invoice_sync is None:
                skipped += 1
                continue

            try:
                current = self.invoice_manager.get_payment(ps.quickbooks_payment_id)
                qb_payment = Payment(
                    Id=ps.quickbooks_payment_id,
                    SyncToken=current.SyncToken if current else '0',
                    sparse=True,
                    CustomerRef=current.CustomerRef if current else CustomerRef(
                        value=invoice_sync.quickbooks_customer_sync.quickbooks_customer_id,
                        name=invoice_sync.quickbooks_customer_sync.customer_display_name,
                    ),
                    TotalAmt=float(ps.amount),
                    Line=[{
                        'Amount': float(ps.amount),
                        'LinkedTxn': [{
                            'TxnId': invoice_sync.quickbooks_invoice_id,
                            'TxnType': 'Invoice',
                        }],
                    }],
                )
                self.invoice_manager.update_payment(qb_payment)
            except Exception as e:
                errors.append({'payment_sync_id': str(ps.id), 'error': str(e)})
                continue

            with transaction.atomic():
                ps.related_invoice = invoice_sync
                ps.needs_review = False
                ps.review_note = 'relinked to invoice via reconciliation'
                ps.save(update_fields=['related_invoice', 'needs_review', 'review_note'])

                invoice_sync.balance_remaining = max(
                    Decimal('0'), invoice_sync.balance_remaining - ps.amount
                )
                invoice_sync.is_paid = invoice_sync.balance_remaining == Decimal('0')
                invoice_sync.save(update_fields=['balance_remaining', 'is_paid'])
            relinked += 1

        return {'relinked': relinked, 'skipped': skipped,
                'error_count': len(errors), 'errors': errors}

    # ------------------------------------------------------------------
    # Correction propagation: re-push a linked invoice after a local
    # discount / fine / waiver / reversal / charge removal changed a
    # FinanceFee balance without going through the charge/payment path.
    # ------------------------------------------------------------------

    def _effective_line_amount(self, line_sync) -> Decimal:
        """QuickBooks line amount that keeps QB ``Balance`` equal to the local
        outstanding balance for this charge.

        QuickBooks derives Balance = TotalAmt - applied payments. Discounts,
        fines, waivers and reversals move ``FinanceFee.balance`` locally with
        no matching QuickBooks payment, so we set the line to
        ``FinanceFee.balance + payments already synced for this charge`` -
        then QB Balance == local balance regardless of what adjusted it.
        """
        fee = line_sync.finance_fee
        synced_payments = QuickBooksFeePaymentSync.objects.filter(
            tenant=self.tenant, sync_status='synced',
            fee_transaction__student_id=fee.student_id,
            fee_transaction__fee_category_id=fee.fee_category_id,
            fee_transaction__academic_year_id=fee.academic_year_id,
            fee_transaction__transaction_type='payment',
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        return Decimal(str(fee.balance)) + Decimal(str(synced_payments))

    def resync_family_invoice(self, family_invoice) -> Optional[QuickBooksFeeInvoiceSync]:
        """Re-push a already-linked consolidated invoice to QuickBooks after a
        local correction. No-op when the invoice was never synced (the normal
        charge-sync path will create it). Preserves any lines the school added
        directly in QuickBooks. Single writer of QB invoice state.
        """
        header = QuickBooksFeeInvoiceSync.objects.filter(
            tenant=self.tenant, family_invoice=family_invoice,
        ).select_related('quickbooks_customer_sync', 'academic_year').first()
        if (header is None or not header.quickbooks_invoice_id
                or header.sync_status != 'synced'):
            return None

        customer_sync = header.quickbooks_customer_sync
        item_ref = self._service_item_ref()
        academic_year = header.academic_year
        currency = CurrencyConfiguration.get_active_currency(self.tenant)
        currency_code = currency.currency_code
        currency_ref = None
        if currency_code and currency_code != 'USD':
            currency_ref = {'value': currency_code, 'name': currency_code}
        custom_fields = [
            {"DefinitionId": "2", "Name": "AcademicYear",
             "StringValue": academic_year.name if academic_year else ""},
        ]

        start_time = timezone.now()
        try:
            with transaction.atomic():
                header = (
                    QuickBooksFeeInvoiceSync.objects.select_for_update().get(pk=header.pk)
                )
                line_syncs = list(header.lines.all().order_by('created_at'))
                our_known_ids = {ls.qb_line_id for ls in line_syncs if ls.qb_line_id}

                current = self.invoice_manager.get_invoice(header.quickbooks_invoice_id)
                current_lines = list(getattr(current, 'Line', None) or [])
                foreign_lines = [
                    cl for cl in current_lines
                    if isinstance(cl, dict) and cl.get('Id')
                    and cl.get('Id') not in our_known_ids
                    and cl.get('DetailType') == 'SalesItemLineDetail'
                ]
                foreign_ids = {cl['Id'] for cl in foreign_lines}

                qb_lines = list(foreign_lines)
                kept = []
                for ls in line_syncs:
                    if ls.finance_fee_id is None:
                        # Underlying charge was removed - drop the line.
                        QuickBooksFeeInvoiceLineSync.objects.filter(pk=ls.pk).update(
                            sync_status='cancelled', synced_at=timezone.now())
                        continue
                    amount = self._effective_line_amount(ls)
                    qb_lines.append(Line(
                        Id=ls.qb_line_id or None,
                        LineNum=len(qb_lines) + 1,
                        Amount=float(amount),
                        Description=ls.description,
                        DetailType='SalesItemLineDetail',
                        SalesItemLineDetail={
                            'ItemRef': item_ref,
                            'UnitPrice': float(amount),
                            'Qty': 1,
                        },
                    ).dict(exclude_none=True))
                    kept.append((ls, amount))

                if not qb_lines:
                    logger.warning(
                        "resync_family_invoice %s: no lines to send; skipping",
                        family_invoice.id)
                    return header

                qb_invoice = Invoice(
                    Id=header.quickbooks_invoice_id,
                    SyncToken=current.SyncToken if current else '0',
                    sparse=True,
                    CustomerRef=CustomerRef(
                        value=customer_sync.quickbooks_customer_id,
                        name=customer_sync.customer_display_name,
                    ),
                    Line=qb_lines,
                    CurrencyRef=currency_ref,
                    CustomField=custom_fields,
                )
                saved = self.invoice_manager.update_invoice(qb_invoice)

                our_saved = [
                    sl for sl in (saved.Line or [])
                    if isinstance(sl, dict)
                    and sl.get('DetailType') == 'SalesItemLineDetail'
                    and sl.get('Id') not in foreign_ids
                ]
                for (ls, amount), sl in zip(kept, our_saved):
                    updates = {'amount': amount, 'sync_status': 'synced',
                               'synced_at': timezone.now()}
                    if sl.get('Id'):
                        updates['qb_line_id'] = sl['Id']
                    QuickBooksFeeInvoiceLineSync.objects.filter(pk=ls.pk).update(**updates)

                header.balance_remaining = Decimal(str(
                    saved.Balance if saved.Balance is not None else header.balance_remaining))
                header.is_paid = header.balance_remaining <= Decimal('0')
                header.synced_at = timezone.now()
                header.sync_status = 'synced'
                header.sync_error = None
                header.save()

            self._log_sync(
                'invoice', 'update', 'success',
                'QuickBooksFeeInvoiceSync', str(header.id), header.quickbooks_invoice_id,
                {'reason': 'correction_resync',
                 'balance_remaining': str(header.balance_remaining),
                 'intuit_tid': self.invoice_manager.last_intuit_tid},
                None, (timezone.now() - start_time).total_seconds(),
            )
            return header

        except Exception as e:
            logger.error(f"resync_family_invoice failed for {family_invoice.id}: {e}")
            QuickBooksFeeInvoiceSync.objects.filter(pk=header.pk).update(
                sync_error=str(e), needs_review=True)
            self._log_sync(
                'invoice', 'update', 'failed',
                'QuickBooksFeeInvoiceSync', str(header.id), header.quickbooks_invoice_id,
                {'reason': 'correction_resync'}, str(e),
                (timezone.now() - start_time).total_seconds(),
            )
            raise BusinessLogicException(f"Failed to resync family invoice: {e}")