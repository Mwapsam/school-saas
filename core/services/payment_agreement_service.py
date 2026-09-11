"""
Payment Agreement Service

Handles creation, management, and payment recording for payment agreements.
Payment agreements are formal documents for collecting outstanding student fees
with an agreed installment schedule.
"""
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.db.models import Sum, QuerySet

from core.models import (
    PaymentAgreement, PaymentAgreementInstallment, PaymentAgreementPaymentRecord,
    Student, Guardian, FinanceFee, FeeTransaction, User,
)
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    BusinessLogicException,
)
from .logging_service import ServiceLogger, logged_operation
from .currency_service import CurrencyService
from .fee_statement_service import FeeStatementService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PaymentAgreementService(TenantAwareService[PaymentAgreement]):
    """Service for managing payment agreements for students."""

    def __init__(self, tenant):
        super().__init__(PaymentAgreement, tenant)
        self.logger = ServiceLogger('payment_agreement', tenant)

    @logged_operation(
        action='create_agreement',
        resource_type='payment_agreement',
        log_result=True
    )
    @transaction.atomic
    def create_agreement(
        self,
        student_id: str,
        debtor_name: str,
        unpaid_fees_amount: Decimal,
        installments: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        guardian_id: Optional[str] = None,
        nrc_number: Optional[str] = None,
        debtor_address: Optional[str] = None,
        other_amount: Decimal = Decimal('0.00'),
        other_description: Optional[str] = None,
        interest_rate: Decimal = Decimal('5.00'),
        created_by: Optional[User] = None,
        **kwargs
    ) -> PaymentAgreement:
        """
        Create a new payment agreement for a student.

        Args:
            student_id: UUID of the student
            debtor_name: Name of the debtor (typically parent/guardian)
            unpaid_fees_amount: Amount of unpaid fees
            installments: List of dicts with 'due_date' and 'amount' keys
            start_date: Agreement start date
            end_date: Agreement end date
            guardian_id: Optional Guardian FK for reference
            nrc_number: NRC/ID number of debtor
            debtor_address: Physical address of debtor
            other_amount: Any additional amount owed (non-fee)
            other_description: Description of other amount
            interest_rate: Late payment interest rate (default 5%)
            created_by: User creating the agreement
            **kwargs: Additional fields

        Returns:
            PaymentAgreement instance with installments created

        Raises:
            NotFoundException: Student not found
            ValidationException: Invalid data or installment totals don't match
        """
        # Validate student exists
        try:
            student = Student.objects.get(id=student_id, tenant=self.tenant)
        except Student.DoesNotExist:
            raise NotFoundException(
                f"Student with id {student_id} not found",
                details={"student_id": student_id}
            )

        # Validate guardian if provided
        guardian = None
        if guardian_id:
            try:
                guardian = Guardian.objects.get(id=guardian_id, tenant=self.tenant)
            except Guardian.DoesNotExist:
                raise NotFoundException(
                    f"Guardian with id {guardian_id} not found",
                    details={"guardian_id": guardian_id}
                )

        # Validate installments
        if not installments or len(installments) == 0:
            raise ValidationException(
                "At least one installment is required",
                details={}
            )

        for i, inst in enumerate(installments):
            if not inst.get('due_date') or not inst.get('amount'):
                raise ValidationException(
                    f"Installment {i+1} is missing due_date or amount",
                    details={"installment_index": i}
                )
            if inst['amount'] <= 0:
                raise ValidationException(
                    f"Installment {i+1} amount must be positive",
                    details={"installment_index": i}
                )

        # Compute total from installments
        total_from_installments = sum(
            Decimal(str(inst['amount'])) for inst in installments
        )
        expected_total = unpaid_fees_amount + other_amount

        # Validate totals match
        if total_from_installments != expected_total:
            raise ValidationException(
                f"Sum of installments (K{total_from_installments}) does not match "
                f"total amount due (K{expected_total})",
                details={
                    "total_from_installments": str(total_from_installments),
                    "expected_total": str(expected_total),
                }
            )

        # Create the agreement
        agreement = PaymentAgreement.objects.create(
            tenant=self.tenant,
            student=student,
            guardian=guardian,
            debtor_name=debtor_name,
            nrc_number=nrc_number,
            debtor_address=debtor_address,
            unpaid_fees_amount=unpaid_fees_amount,
            other_amount=other_amount,
            other_description=other_description,
            total_amount=expected_total,
            start_date=start_date,
            end_date=end_date,
            interest_rate=interest_rate,
            status='draft',
            created_by=created_by,
        )

        # Create installments
        for i, inst_data in enumerate(installments, start=1):
            PaymentAgreementInstallment.objects.create(
                tenant=self.tenant,
                agreement=agreement,
                sequence=i,
                due_date=inst_data['due_date'],
                amount=Decimal(str(inst_data['amount'])),
            )

        return agreement

    @logged_operation(
        action='record_payment',
        resource_type='payment_agreement',
        log_result=True
    )
    @transaction.atomic
    def record_payment(
        self,
        agreement_id: str,
        amount_paid: Decimal,
        payment_date: date,
        recorded_by: Optional[User] = None,
        fee_transaction: Optional[FeeTransaction] = None,
    ) -> PaymentAgreementPaymentRecord:
        """
        Record a payment against an agreement.

        Appends a payment record, updates running balance, and marks agreement
        as 'completed' if all installments are paid.

        Note: balance_after is computed from the prior record's balance and stored
        as a denormalized field. This method assumes payment records are only created,
        never edited or deleted after creation. If a future delete/edit endpoint is
        added, all subsequent balance_after values must be recomputed to stay
        consistent.

        Args:
            agreement_id: UUID of the agreement
            amount_paid: Amount paid
            payment_date: Date of payment
            recorded_by: User recording the payment
            fee_transaction: Optional link to FeeTransaction if recorded via Collect Fees

        Returns:
            PaymentAgreementPaymentRecord instance

        Raises:
            NotFoundException: Agreement not found
            ValidationException: Invalid amount or agreement status
        """
        try:
            agreement = PaymentAgreement.objects.get(id=agreement_id, tenant=self.tenant)
        except PaymentAgreement.DoesNotExist:
            raise NotFoundException(
                f"Payment agreement with id {agreement_id} not found",
                details={"agreement_id": agreement_id}
            )

        if agreement.status not in ['draft', 'active']:
            raise ValidationException(
                f"Cannot record payment on agreement with status '{agreement.status}'",
                details={"status": agreement.status}
            )

        if amount_paid <= 0:
            raise ValidationException(
                "Payment amount must be positive",
                details={"amount_paid": str(amount_paid)}
            )

        # Calculate running balance
        # Get previous balance from last payment record, or start with agreement total
        last_record = agreement.payment_records.order_by('-payment_date').first()
        if last_record:
            previous_balance = last_record.balance_after
        else:
            previous_balance = agreement.total_amount

        balance_after = previous_balance - amount_paid

        if balance_after < 0:
            raise ValidationException(
                f"Payment of K{amount_paid} exceeds remaining balance of K{previous_balance}",
                details={
                    "amount_paid": str(amount_paid),
                    "remaining_balance": str(previous_balance),
                }
            )

        # Create payment record
        payment_record = PaymentAgreementPaymentRecord.objects.create(
            tenant=self.tenant,
            agreement=agreement,
            payment_date=payment_date,
            amount_paid=amount_paid,
            balance_after=balance_after,
            recorded_by=recorded_by,
            fee_transaction=fee_transaction,
        )

        # Update agreement status if fully paid
        if balance_after == 0:
            agreement.status = 'completed'
            agreement.save()

        # If still draft, transition to active on first payment
        if agreement.status == 'draft':
            agreement.status = 'active'
            agreement.save()

        return payment_record

    def get_agreement_context(self, agreement_id: str) -> Dict[str, Any]:
        """
        Get full context for rendering agreement detail/PDF.

        Returns dict with:
            - agreement: PaymentAgreement instance
            - installments: list of installments with ordinal labels
            - payment_records: list of payment records with running totals
            - running_balance: current outstanding balance
            - currency_symbol: from CurrencyService
            - paid_total: total paid so far
            - installments_due: number of installments not yet past due
            - all_guardians: list of all guardians linked to the student, with relation labels
            - payment_records_by_sequence: dict mapping instalment sequence -> payment record for easy lookup

        Raises:
            NotFoundException: Agreement not found
        """
        try:
            agreement = PaymentAgreement.objects.get(id=agreement_id, tenant=self.tenant)
        except PaymentAgreement.DoesNotExist:
            raise NotFoundException(
                f"Payment agreement with id {agreement_id} not found",
                details={"agreement_id": agreement_id}
            )

        installments = list(agreement.installments.all().order_by('sequence'))
        payment_records = list(agreement.payment_records.all().order_by('payment_date'))

        # Calculate totals
        paid_total = sum(Decimal(str(r.amount_paid)) for r in payment_records) or Decimal('0.00')
        running_balance = agreement.total_amount - paid_total

        # Count installments past due (today > due_date)
        from django.utils import timezone
        today = timezone.now().date()
        installments_due = sum(1 for inst in installments if inst.due_date < today)

        # Ordinal suffixes for instalment numbering
        ordinal_map = {1: 'st', 2: 'nd', 3: 'rd'}

        # Add ordinal labels to installments
        for inst in installments:
            suffix = ordinal_map.get(inst.sequence, 'th')
            inst.ordinal_label = f"{inst.sequence}{suffix} Instalment"

        # Build installments with paired payment records for template rendering
        # Positional matching: Nth installment pairs with Nth payment record (if exists)
        installments_with_records = []
        for i, inst in enumerate(installments):
            record = payment_records[i] if i < len(payment_records) else None
            installments_with_records.append({
                'installment': inst,
                'payment_record': record,
            })

        # Get all guardians linked to the student via StudentGuardianRelation
        from core.models import StudentGuardianRelation, Guardian
        guardians = Guardian.objects.filter(
            student_relations__student=agreement.student,
            student_relations__tenant=self.tenant,
            is_active=True,
        ).distinct().prefetch_related('student_relations')

        all_guardians = []
        for guardian in guardians:
            # Get the relation label from StudentGuardianRelation
            relation_obj = guardian.student_relations.filter(student=agreement.student).first()
            relation_label = relation_obj.relation if relation_obj else 'Guardian'
            is_primary_contact = bool(relation_obj and relation_obj.is_immediate_contact)

            # Build address string
            address_parts = [
                guardian.office_address_line1,
                guardian.office_address_line2,
                guardian.city,
                guardian.state,
            ]
            address_str = ', '.join(part for part in address_parts if part)

            # Pick phone (prefer mobile, then office)
            phone = guardian.mobile_phone or guardian.office_phone or ''

            is_debtor = guardian.id == agreement.guardian_id if agreement.guardian_id else False

            all_guardians.append({
                'guardian': guardian,
                'relation': relation_label,
                'full_name': str(guardian),
                'address': address_str,
                'phone': phone,
                'email': guardian.email or '',
                'is_debtor': is_debtor,
                'is_primary_contact': is_primary_contact,
            })

        # Order so the primary contact (the debtor, else the immediate contact)
        # is rendered first and every other guardian follows, all in the same
        # format on the agreement.
        all_guardians.sort(
            key=lambda g: (not g['is_debtor'], not g['is_primary_contact'], g['full_name'])
        )

        currency_service = CurrencyService(self.tenant)

        # Fetch default school signature for Director/Principal block
        from core.models import SchoolSignature
        head_signature = SchoolSignature.objects.filter(tenant=self.tenant, is_default=True).first()
        director_display_name = ''
        director_signature_url = None
        if head_signature:
            director_display_name = head_signature.name or ''
            if head_signature.image and getattr(head_signature.image, 'url', None):
                director_signature_url = head_signature.image.url
        # Fall back to manually-entered director_name if no default signature is configured
        if not director_display_name and agreement.director_name:
            director_display_name = agreement.director_name

        # Fetch operations manager name for witness field
        operations_manager_name = self.tenant.operations_manager_name or ''

        # Build school full address from address fields
        school_address_parts = [
            self.tenant.address_line1,
            self.tenant.address_line2,
            self.tenant.city,
        ]
        school_full_address = ', '.join(part for part in school_address_parts if part)

        # Extract debtor guardian info for Names of Debtors section
        debtor_guardian_info = None
        for guardian_info in all_guardians:
            if guardian_info['is_debtor']:
                debtor_guardian_info = guardian_info
                break

        return {
            'agreement': agreement,
            'installments': installments,
            'installments_with_records': installments_with_records,
            'payment_records': payment_records,
            'running_balance': running_balance,
            'paid_total': paid_total,
            'installments_due': installments_due,
            'all_guardians': all_guardians,
            'debtor_guardian_info': debtor_guardian_info,
            'currency_symbol': currency_service.get_currency_symbol(),
            'director_display_name': director_display_name,
            'director_signature_url': director_signature_url,
            'operations_manager_name': operations_manager_name,
            'school_full_address': school_full_address,
        }

    def outstanding_by_term(
        self,
        student: Student,
        academic_year=None,
    ) -> Dict[str, Any]:
        """Break a student's outstanding fee balance down per academic term.

        Each outstanding ``FinanceFee`` (balance > 0) is bucketed by the term of
        its fee collection. Charges with no term (or no collection) fall into an
        "Unallocated" bucket so the parts always add up to the whole.

        Returns:
            {
                'rows': [ {'term_id', 'label', 'order', 'amount'}, ... ]  # term order
                'total': Decimal,  # sum of all rows
            }
        """
        qs = FinanceFee.objects.filter(
            tenant=self.tenant, student=student, balance__gt=0,
        )
        if academic_year is not None:
            qs = qs.filter(academic_year=academic_year)
        qs = qs.select_related('fee_collection', 'fee_collection__term')

        buckets: Dict[Any, Dict[str, Any]] = {}
        for fee in qs:
            collection = fee.fee_collection
            term = collection.term if (collection and collection.term_id) else None
            key = term.id if term else None
            if key not in buckets:
                if term is not None:
                    label = term.name
                    order = term.order
                elif collection is not None:
                    label = collection.name
                    order = 10_000
                else:
                    label = 'Unallocated'
                    order = 20_000
                buckets[key] = {
                    'term_id': str(key) if key else None,
                    'label': label,
                    'order': order,
                    'amount': Decimal('0.00'),
                }
            buckets[key]['amount'] += fee.balance

        rows = sorted(buckets.values(), key=lambda r: (r['order'], r['label']))
        total = sum((r['amount'] for r in rows), Decimal('0.00'))
        return {'rows': rows, 'total': total}

    def get_student_agreements(self, student_id: str) -> QuerySet:
        """Get all agreements for a student."""
        return PaymentAgreement.objects.filter(
            tenant=self.tenant,
            student_id=student_id,
        ).order_by('-created_at')

    def get_agreements_by_status(self, status: str) -> QuerySet:
        """Get all agreements with a specific status."""
        valid_statuses = ['draft', 'active', 'completed', 'defaulted', 'cancelled']
        if status not in valid_statuses:
            raise ValidationException(
                f"Invalid status '{status}'. Must be one of {valid_statuses}",
                details={"status": status}
            )
        return PaymentAgreement.objects.filter(
            tenant=self.tenant,
            status=status,
        ).order_by('-created_at')

    @logged_operation(
        action='bulk_create_agreements',
        resource_type='payment_agreement',
        log_result=True
    )
    def bulk_create_agreements(
        self,
        student_ids: List[str],
        start_date: date,
        end_date: date,
        interest_rate: Decimal = Decimal('5.00'),
        installment_count: int = 3,
        created_by: Optional[User] = None,
    ) -> List[Dict[str, Any]]:
        """
        Create payment agreements for multiple students with shared terms.

        Each student's agreement is created independently with auto-derived values:
        - Debtor: First active guardian linked to the student (skipped if none)
        - Installments: Balance split evenly across installment_count,
          monthly spacing from start_date, remainder absorbed by last installment

        Args:
            student_ids: List of student UUIDs
            start_date: Agreement start date (applies to all)
            end_date: Agreement end date (applies to all)
            interest_rate: Late payment interest rate (default 5%)
            installment_count: Number of monthly installments (default 3)
            created_by: User creating the agreements

        Returns:
            List of dicts with per-student results:
            {
                'student_id': UUID,
                'success': bool,
                'agreement_id': UUID (if success),
                'skipped': bool (if skipped, not an error),
                'error': str (if failed or skipped)
            }

        Notes:
            - Does NOT wrap in a single @transaction.atomic block, so one student's
              failure doesn't roll back others (partial success is acceptable).
            - Each create_agreement call is individually atomic.
            - Students with no active guardian or zero balance are skipped,
              not counted as errors.
        """
        fee_service = FeeStatementService(self.tenant)
        results = []

        for student_id in student_ids:
            result = {
                'student_id': student_id,
                'success': False,
                'skipped': False,
                'error': None,
            }

            try:
                # Fetch student
                student = Student.objects.get(id=student_id, tenant=self.tenant)
            except Student.DoesNotExist:
                result['error'] = 'Student not found'
                results.append(result)
                continue

            try:
                # Get student's outstanding balance
                outstanding_qs = FinanceFee.objects.filter(
                    tenant=self.tenant,
                    student=student,
                    balance__gt=0,
                )
                outstanding_balance = outstanding_qs.aggregate(
                    total=Sum('balance')
                )['total'] or Decimal('0.00')

                # Skip if no balance
                if outstanding_balance <= 0:
                    result['skipped'] = True
                    result['error'] = 'No outstanding balance'
                    results.append(result)
                    continue

                # Get primary guardian
                guardians = fee_service.get_student_guardians(student)
                if not guardians:
                    result['skipped'] = True
                    result['error'] = 'No guardian on file'
                    results.append(result)
                    continue

                primary_guardian = guardians[0]  # First active guardian
                debtor_name = f"{primary_guardian.first_name} {primary_guardian.last_name}".strip()

                # Build installments: evenly split balance across months
                installments = []
                base_amount = outstanding_balance / Decimal(str(installment_count))
                remainder = outstanding_balance - (base_amount * Decimal(str(installment_count - 1)))

                # Calculate total days and evenly distribute due dates
                total_days = (end_date - start_date).days

                for i in range(installment_count):
                    # Evenly distribute due dates from start_date to end_date
                    # Last installment always due on end_date
                    if i == installment_count - 1:
                        due_date = end_date
                    else:
                        progress = (i + 1) / installment_count
                        due_date = start_date + timedelta(days=int(total_days * progress))

                    # Last installment gets the remainder
                    amount = remainder if i == installment_count - 1 else base_amount

                    installments.append({
                        'due_date': due_date,
                        'amount': amount,
                    })

                # Create agreement
                agreement = self.create_agreement(
                    student_id=student_id,
                    debtor_name=debtor_name,
                    unpaid_fees_amount=outstanding_balance,
                    installments=installments,
                    start_date=start_date,
                    end_date=end_date,
                    guardian_id=str(primary_guardian.id),
                    other_amount=Decimal('0.00'),
                    interest_rate=interest_rate,
                    created_by=created_by,
                )

                result['success'] = True
                result['agreement_id'] = str(agreement.id)

            except ValidationException as e:
                result['error'] = str(e)
            except Exception as e:
                logger.error(f"Error creating agreement for student {student_id}: {e}", exc_info=True)
                result['error'] = f"Error: {str(e)}"

            results.append(result)

        return results
