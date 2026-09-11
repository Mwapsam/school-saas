from typing import Dict, Any, Tuple, List, Optional
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.db.models import F, Q, QuerySet, Sum
from django.utils import timezone

from core.models import (
    FinanceTransaction, FinanceTransactionCategory, FeeCategory,
    BatchFeeCategory, BatchFeeCategoryStudent, FinanceFee, Student, Employee, Batch, FeeTransaction,
    AcademicYear, FeeDiscount, FineSlab, FeeWaiver, FeeParticular, FeeApplicabilityRule,
    StudentCategory, FeeMasterParticular, FeeMasterDiscount, FeeReceiptSettings,
    FamilyInvoiceLine, BatchStudent,
)

# Valid lowercase payment-method codes accepted by the FinanceTransaction /
# FeeTransaction models. Used to normalise free-form input (e.g. "Cash").
VALID_PAYMENT_METHODS = {'cash', 'card', 'bank_transfer', 'mobile_money', 'cheque', 'online', 'other'}


def normalize_payment_method(value: str) -> str:
    """Map free-form payment-method text to a valid lowercase model choice."""
    if not value:
        return 'cash'
    v = str(value).strip().lower().replace(' ', '_')
    if v in VALID_PAYMENT_METHODS:
        return v
    # Common aliases
    aliases = {
        'credit_card': 'card', 'debit_card': 'card', 'visa': 'card', 'mastercard': 'card',
        'bank': 'bank_transfer', 'transfer': 'bank_transfer',
        'momo': 'mobile_money', 'mtn': 'mobile_money', 'airtel': 'mobile_money',
        'check': 'cheque',
    }
    return aliases.get(v, 'other')
from .base import TenantAwareService
from .exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateException,
    BusinessLogicException
)
from .logging_service import ServiceLogger, logged_operation
from .invoice_service import InvoiceService
from .qb_sync_helpers import enqueue_qb_sync


class FinanceService(TenantAwareService[FinanceTransaction]):
    def __init__(self, tenant):
        super().__init__(FinanceTransaction, tenant)
        self.logger = ServiceLogger('finance', tenant)

    def get_active_academic_year(self) -> AcademicYear:
        """Return the tenant's active academic year (or None if none is set)."""
        return AcademicYear.objects.filter(
            tenant=self.tenant, is_active=True
        ).first()

    def _log_ledger_event(self, action: str, fee_transaction: FeeTransaction, student,
                          academic_year, user=None, extra: Dict[str, Any] = None):
        """Write an auditable record of a balance-affecting fee event.

        Pairs the immutable FeeTransaction ledger row with a ServiceLogger entry
        carrying the actor + academic year, so the financial audit trail and the
        ledger reconcile (Phase 6).
        """
        details = {
            'event': action,
            'fee_transaction_id': str(fee_transaction.id),
            'transaction_type': fee_transaction.transaction_type,
            'amount': str(fee_transaction.amount),
            'student': getattr(student, 'admission_no', str(getattr(student, 'id', ''))),
            'academic_year': str(academic_year) if academic_year else None,
        }
        if extra:
            details.update(extra)
        self.logger.log_create(
            resource_type='fee_ledger_event',
            resource_id=str(fee_transaction.id),
            user=user,
            details=details,
        )

    def _enqueue_qb_sync(self, kind: str, object_id) -> None:
        """Thin wrapper over the shared qb_sync_helpers.enqueue_qb_sync, kept
        so existing FinanceService call sites don't need to change."""
        enqueue_qb_sync(self.tenant, kind, object_id)

    def _enqueue_qb_invoice_resync(self, finance_fee) -> None:
        """Schedule a QuickBooks re-push of the consolidated invoice this
        charge belongs to, after a local correction changed its balance
        outside the charge/payment path. No-op if the charge has no invoice
        line (or QuickBooks is not connected)."""
        if finance_fee is None:
            return
        invoice_id = FamilyInvoiceLine.objects.filter(
            tenant=self.tenant, finance_fee=finance_fee,
        ).values_list('invoice_id', flat=True).first()
        if invoice_id:
            self._enqueue_qb_sync('invoice_resync', invoice_id)

    @logged_operation(action='create', resource_type='financial_transaction', log_result=True)
    @transaction.atomic
    def create_transaction(
        self,
        title: str,
        amount: Decimal,
        category_id: str,
        transaction_date: date = None,
        description: str = None,
        student_id: str = None,
        employee_id: str = None,
        academic_year: AcademicYear = None,
        user=None,
        **additional_data
    ) -> FinanceTransaction:
        if transaction_date is None:
            transaction_date = date.today()

        if amount <= 0:
            raise ValidationException(
                "Transaction amount must be positive",
                details={"amount": amount}
            )

        category = self._get_transaction_category_by_id(category_id)

        student = None
        if student_id:
            student = self._get_student_by_id(student_id)

        employee = None
        if employee_id:
            employee = self._get_employee_by_id(employee_id)

        if academic_year is None:
            academic_year = self.get_active_academic_year()

        transaction_data = {
            "title": title,
            "amount": amount,
            "category": category,
            "transaction_date": transaction_date,
            "description": description,
            "student": student,
            "employee": employee,
            "academic_year": academic_year,
            "tenant": self.tenant,
            **additional_data
        }
        
        transaction_obj = FinanceTransaction.objects.create(**transaction_data)
        
        self.logger.log_create(
            resource_type='financial_transaction',
            resource_id=str(transaction_obj.id),
            user=user,
            details={
                'title': title,
                'amount': str(amount),
                'category': category.name,
                'transaction_date': str(transaction_date),
                'student': f"{student.first_name} {student.last_name}" if student else None,
                'employee': f"{employee.first_name} {employee.last_name}" if employee else None
            }
        )
        
        return transaction_obj
    
    def get_transactions_by_date_range(
        self, 
        start_date: date, 
        end_date: date,
        category_id: str = None,
        student_id: str = None
    ) -> QuerySet[FinanceTransaction]:
        query = Q(
            tenant=self.tenant,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )
        
        if category_id:
            query &= Q(category_id=category_id)
        
        if student_id:
            query &= Q(student_id=student_id)
        
        return FinanceTransaction.objects.filter(query).order_by('-transaction_date')
    
    def get_income_transactions(
        self, 
        start_date: date = None, 
        end_date: date = None
    ) -> QuerySet[FinanceTransaction]:
        query = Q(tenant=self.tenant, category__is_income=True)
        
        if start_date:
            query &= Q(transaction_date__gte=start_date)
        
        if end_date:
            query &= Q(transaction_date__lte=end_date)
        
        return FinanceTransaction.objects.filter(query).order_by('-transaction_date')
    
    def get_expense_transactions(
        self, 
        start_date: date = None, 
        end_date: date = None
    ) -> QuerySet[FinanceTransaction]:
        query = Q(tenant=self.tenant, category__is_income=False)
        
        if start_date:
            query &= Q(transaction_date__gte=start_date)
        
        if end_date:
            query &= Q(transaction_date__lte=end_date)
        
        return FinanceTransaction.objects.filter(query).order_by('-transaction_date')
    
    def create_fee_category(
        self,
        name: str,
        description: str = None,
        **additional_data
    ) -> FeeCategory:
        if FeeCategory.objects.filter(
            name=name,
            tenant=self.tenant,
            is_deleted=False
        ).exists():
            raise DuplicateException(
                f"Fee category '{name}' already exists",
                details={"name": name}
            )
        
        category_data = {
            "name": name,
            "description": description,
            "tenant": self.tenant,
            **additional_data
        }
        # Default to the active academic year unless the caller specified one.
        category_data.setdefault("academic_year", self.get_active_academic_year())

        return FeeCategory.objects.create(**category_data)
    
    def get_fee_categories(self, active_only: bool = True) -> QuerySet[FeeCategory]:
        query = Q(tenant=self.tenant)
        
        if active_only:
            query &= Q(is_deleted=False)
        
        return FeeCategory.objects.filter(query)
    
    @logged_operation('assign_fee_to_batches')
    @transaction.atomic
    def assign_fee_to_batches(
        self,
        fee_category_id: str,
        batch_ids: List[str],
        student_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create BatchFeeCategory rows for each batch (skipping ones that
        already exist — same dedupe as today's view-level loop). If
        student_ids is given, for EACH batch intersect student_ids with that
        batch's actual BatchStudent roster — a student not enrolled in a given
        batch is excluded from that batch's scoping, never added globally. If
        intersection is empty for a batch, surface that for admin warning."""

        fee_category = FeeCategory.objects.filter(
            tenant=self.tenant, id=fee_category_id, is_deleted=False
        ).first()
        if not fee_category:
            raise NotFoundException(f"Fee category {fee_category_id} not found")

        batches = Batch.objects.filter(
            tenant=self.tenant, id__in=batch_ids, is_deleted=False
        )
        if not batches.exists():
            raise ValidationException("No valid batches found")

        created_count = 0
        skipped_batches = []
        assignment_ids = []
        zero_student_batches = []

        for batch in batches:
            if BatchFeeCategory.objects.filter(
                tenant=self.tenant, fee_category=fee_category, batch=batch
            ).exists():
                skipped_batches.append(batch.name)
                continue

            bfc = BatchFeeCategory.objects.create(
                tenant=self.tenant, fee_category=fee_category, batch=batch
            )
            created_count += 1
            assignment_ids.append(str(bfc.id))

            if student_ids:
                enrolled_ids = set(
                    BatchStudent.objects.filter(
                        tenant=self.tenant, batch=batch, student_id__in=student_ids
                    ).values_list('student_id', flat=True)
                )
                if enrolled_ids:
                    BatchFeeCategoryStudent.objects.bulk_create([
                        BatchFeeCategoryStudent(
                            tenant=self.tenant,
                            batch_fee_category=bfc,
                            student_id=sid
                        )
                        for sid in enrolled_ids
                    ])
                else:
                    zero_student_batches.append(batch.name)

        return {
            'created_count': created_count,
            'skipped_batches': skipped_batches,
            'assignment_ids': assignment_ids,
            'zero_student_batches': zero_student_batches,
        }

    @logged_operation('bulk_delete_batch_fee_assignments')
    @transaction.atomic
    def bulk_delete_batch_fee_assignments(
        self, assignment_ids: List[str]
    ) -> Dict[str, Any]:
        """Delete multiple BatchFeeCategory rows. No business-rule blocking
        condition exists, so a single tenant-scoped filtered delete is
        sufficient; CASCADE cleans up BatchFeeCategoryStudent rows automatically."""

        qs = BatchFeeCategory.objects.filter(
            tenant=self.tenant, id__in=assignment_ids
        )
        found_ids = list(qs.values_list('id', flat=True))
        deleted_count, _ = qs.delete()
        return {
            'deleted_count': len(found_ids),
            'found_ids': [str(i) for i in found_ids],
        }

    @transaction.atomic
    def upsert_fee_particular(
        self,
        fee_category_id: str,
        particular_id: str = None,
        user=None,
        reason: str = None,
        **fields
    ) -> FeeParticular:
        """Single write path for creating/updating a FeeParticular. Keeps
        BatchFeeCategory.amount in sync (summed from active particulars) for
        every batch this category is assigned to. Logs amount changes to
        FeeAmountChangeLog if user is provided."""
        from core.models import FeeAmountChangeLog

        fee_category = self._get_fee_category_by_id(fee_category_id)

        if particular_id:
            particular = FeeParticular.objects.filter(
                tenant=self.tenant, id=particular_id, fee_category=fee_category
            ).first()
            if not particular:
                raise NotFoundException(
                    "Fee particular not found",
                    details={"particular_id": particular_id}
                )

            # Log amount change if it's being updated
            old_amount = particular.amount
            for key, value in fields.items():
                setattr(particular, key, value)

            # Create audit log if amount changed and user provided
            if 'amount' in fields and old_amount != fields['amount'] and user:
                FeeAmountChangeLog.objects.create(
                    tenant=self.tenant,
                    fee_particular=particular,
                    old_amount=old_amount,
                    new_amount=fields['amount'],
                    changed_by=user,
                    reason=reason
                )

            particular.save()
        else:
            particular = FeeParticular.objects.create(
                tenant=self.tenant, fee_category=fee_category, **fields
            )

        return particular

    def delete_fee_particular(self, particular_id):
        """Soft-delete a FeeParticular (is_active=False). Raises NotFoundException if
        missing, BusinessLogicException if it's already referenced by billing records —
        FeeTransaction.fee_particular is CASCADE, so this never hard-deletes."""
        from core.models import FinanceFeeItem

        particular = FeeParticular.objects.filter(
            tenant=self.tenant, id=particular_id, is_active=True
        ).first()
        if not particular:
            raise NotFoundException("Fee particular not found", details={"particular_id": particular_id})

        if FinanceFeeItem.objects.filter(tenant=self.tenant, fee_particular=particular).exists() or \
           FeeTransaction.objects.filter(tenant=self.tenant, fee_particular=particular).exists():
            raise BusinessLogicException("Cannot delete: this particular has already been billed to students")

        particular.is_active = False
        particular.save(update_fields=['is_active'])

    @transaction.atomic
    def record_student_fee(
        self,
        student_id: str,
        fee_category_id: str,
        balance: Decimal,
        transaction_date: date = None,
        academic_year: AcademicYear = None
    ) -> FinanceFee:
        if transaction_date is None:
            transaction_date = date.today()

        student = self._get_student_by_id(student_id)

        fee_category = self._get_fee_category_by_id(fee_category_id)

        if academic_year is None:
            # Prefer the year the fee category belongs to, else the active year.
            academic_year = fee_category.academic_year or self.get_active_academic_year()

        fee_data = {
            "student": student,
            "fee_category": fee_category,
            "balance": balance,
            "transaction_date": transaction_date,
            "academic_year": academic_year,
            "tenant": self.tenant
        }

        finance_fee = FinanceFee.objects.create(**fee_data)

        # Record the charge as a ledger entry so balances are always derivable
        # from the FeeTransaction ledger (the single primitive) and statements
        # reflect the original charge, not just the running balance.
        if balance and balance > 0:
            FeeTransaction.objects.create(
                tenant=self.tenant, student=student, fee_category=fee_category,
                academic_year=academic_year, transaction_type='adjustment',
                amount=balance, description=f"Fee charge: {fee_category.name}",
            )

        # Upsert the guardian's consolidated local invoice synchronously - this
        # is pure local data and must be authoritative immediately so the
        # parent-portal PDF always reflects the latest charge.
        InvoiceService(self.tenant).upsert_guardian_invoice(finance_fee)

        # Mirror the charge to QuickBooks as an invoice line (async, after commit).
        self._enqueue_qb_sync('charge', finance_fee.id)

        return finance_fee
    
    def _assert_not_duplicate_payment(self, student, fee_category, amount, reference, academic_year):
        """Guard against accidentally posting the same payment twice.

        - If a reference/receipt number is supplied, it must be unique among the
          student's payments (a receipt identifies exactly one payment).
        - Otherwise, reject an identical payment (same student/category/amount/year)
          recorded within the last few seconds (double-submit protection).
        """
        base = FeeTransaction.objects.filter(
            tenant=self.tenant, student=student, transaction_type='payment',
            amount=amount,
        )
        if academic_year is not None:
            base = base.filter(academic_year=academic_year)

        if reference:
            if base.filter(reference_number=reference).exists():
                raise DuplicateException(
                    "A payment with this reference has already been recorded",
                    details={"reference_number": reference},
                )
        else:
            window_start = timezone.now() - timedelta(seconds=10)
            if base.filter(
                fee_category=fee_category, transaction_date__gte=window_start
            ).exists():
                raise DuplicateException(
                    "An identical payment was just recorded; possible double submission",
                    details={"amount": str(amount), "fee_category": fee_category.name},
                )

    def _assert_reference_not_reused(self, student, reference):
        """Reference-only duplicate guard for a whole itemized submission.

        Used instead of ``_assert_not_duplicate_payment`` when one payment
        spans several categories/particulars sharing a single reference
        number - checking per-line would falsely flag the submission's own
        later lines as duplicates of its earlier ones.
        """
        if reference and FeeTransaction.objects.filter(
            tenant=self.tenant, student=student, transaction_type='payment',
            reference_number=reference,
        ).exists():
            raise DuplicateException(
                "A payment with this reference has already been recorded",
                details={"reference_number": reference},
            )

    def _generate_receipt_reference(self) -> str:
        """A stable grouping key for a payment submission's FeeTransaction
        row(s), used when the cashier doesn't supply their own reference.
        Sequential and school-branded (e.g. "PW7022"), configured per-tenant
        via FeeReceiptSettings."""
        return FeeReceiptSettings.allocate_receipt_number(self.tenant)

    def _allocate_amount_across_particulars(
        self, fee_category, amount: Decimal
    ) -> List[Tuple[Optional["FeeParticular"], Decimal]]:
        """Split a lump-sum ``amount`` across ``fee_category``'s active
        particulars, oldest due date first, so the resulting FeeTransaction
        rows are always tagged to a specific particular (same shape as an
        itemized payment). Falls back to a single untagged allocation when
        the category has no particulars defined.
        """
        particulars = list(
            FeeParticular.objects.filter(
                tenant=self.tenant, fee_category=fee_category, is_active=True
            ).order_by(F('due_date').asc(nulls_last=True), 'created_at')
        )
        if not particulars:
            return [(None, amount)]

        allocations = []
        remaining = amount
        for particular in particulars:
            if remaining <= 0:
                break
            paid_so_far = FeeTransaction.objects.filter(
                tenant=self.tenant, fee_particular=particular, transaction_type='payment',
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            outstanding = particular.amount - paid_so_far
            if outstanding <= 0:
                continue
            allocated = min(remaining, outstanding)
            allocations.append([particular, allocated])
            remaining -= allocated

        if remaining > 0:
            # Every particular is already settled, or the amount exceeds what's
            # billed (overpayment) - attribute the rest rather than leaving it
            # untagged.
            if allocations:
                allocations[-1][1] += remaining
            else:
                allocations.append([particulars[-1], remaining])

        return [tuple(a) for a in allocations]

    def _apply_fee_payment_effects(
        self, student, fee_category, amount, payment_method, payment_date,
        reference=None, academic_year=None, fee_particular=None,
        skip_duplicate_check=False, collected_by=None, notes=None,
    ):
        """Record the per-student ledger effects of a fee payment:
        - decrement the matching FinanceFee.balance and flip is_paid / has_paid_fees
        - write a FeeTransaction(transaction_type='payment') ledger row

        The FinanceFee lookup is scoped to ``academic_year`` when supplied so a
        payment can only pay down the intended year's charge (never a prior
        year's balance for the same fee category).

        Requires a matching FinanceFee charge: an orphan payment (money recorded
        with no charge to settle) raises BusinessLogicException so the local
        ledger and balances can never silently diverge.
        Returns the affected FinanceFee.
        """
        method = normalize_payment_method(payment_method)
        if not skip_duplicate_check:
            self._assert_not_duplicate_payment(student, fee_category, amount, reference, academic_year)

        fee_query = FinanceFee.objects.filter(
            student=student, fee_category=fee_category, tenant=self.tenant
        )
        if academic_year is not None:
            fee_query = fee_query.filter(academic_year=academic_year)
        student_fee = fee_query.order_by('is_paid', 'created_at').first()

        if student_fee is None:
            raise BusinessLogicException(
                "Cannot record a payment with no matching fee charge for this "
                "student, category and academic year",
                details={
                    "student": getattr(student, 'admission_no', str(student.id)),
                    "fee_category": fee_category.name,
                    "academic_year": str(academic_year) if academic_year else None,
                },
            )

        if student_fee.balance > 0:
            student_fee.balance -= amount
            if student_fee.balance <= 0:
                student_fee.balance = Decimal('0.00')
                student_fee.is_paid = True
            student_fee.save()
            # Mark student fully paid only when no outstanding fees remain. When
            # scoped to a year, this reflects "paid up for that academic year".
            outstanding = FinanceFee.objects.filter(
                student=student, is_paid=False, balance__gt=0, tenant=self.tenant
            )
            if academic_year is not None:
                outstanding = outstanding.filter(academic_year=academic_year)
            if not outstanding.exists():
                student.has_paid_fees = True
                student.save()

        # Per-student fee ledger row (transaction_date is auto_now_add on the model)
        ledger_row = FeeTransaction.objects.create(
            tenant=self.tenant,
            student=student,
            fee_category=fee_category,
            fee_particular=fee_particular,
            academic_year=academic_year,
            transaction_type='payment',
            amount=amount,
            payment_method=method,
            reference_number=reference,
            collected_by=collected_by,
            # Persist the cashier-typed note verbatim so it shows on the
            # statement / receipt; fall back to a generated label when blank.
            description=(notes or '').strip() or (
                f"Fee payment via {method}"
                + (f" ({fee_particular.name})" if fee_particular else "")
            ),
        )
        self._log_ledger_event('payment', ledger_row, student, academic_year)
        # Recompute the guardian's consolidated invoice (amount_paid/balance_due)
        # synchronously - local data, must be authoritative immediately.
        InvoiceService(self.tenant).mark_invoice_paid_if_settled(student_fee)
        # Mirror the payment to QuickBooks (async, after commit), applied to the
        # matching academic year's invoice.
        self._enqueue_qb_sync('payment', ledger_row.id)
        self._notify_payment_received(student, amount, method)
        return student_fee

    def _notify_payment_received(self, student, amount, method) -> None:
        """Tell the student's guardians a payment was recorded, through
        Notification Control (Configuration → Notification Control).
        Best-effort — never blocks a payment."""
        try:
            from core.models import StudentGuardianRelation
            from core.services.notification_service import NotificationService

            relations = (
                StudentGuardianRelation.objects
                .filter(tenant=self.tenant, student=student)
                .select_related('guardian')
            )
            recipients = [
                {
                    "id": r.guardian_id, "type": "guardian",
                    "phone": getattr(r.guardian, 'mobile_phone', None),
                    "email": getattr(r.guardian, 'email', None),
                }
                for r in relations if r.guardian_id
            ]
            name = f"{student.first_name} {student.last_name}".strip()
            NotificationService(self.tenant).dispatch(
                "fee_payment_received", "guardians", recipients,
                title="Payment received",
                message=(
                    f"A payment of {amount} for {name} has been received. "
                    f"Thank you."
                ),
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "fee-payment-received notification failed"
            )

    @transaction.atomic
    def process_fee_payment(
        self,
        student_id: str,
        fee_category_id: str,
        payment_amount: Decimal,
        payment_date: date = None,
        description: str = None,
        payment_method: str = 'cash',
        academic_year: AcademicYear = None,
        reference_number: str = None,
        collected_by_id: str = None,
    ) -> Tuple[FinanceTransaction, FinanceFee]:
        if payment_date is None:
            payment_date = date.today()

        collected_by = self._get_employee_by_id(collected_by_id) if collected_by_id else None

        if payment_amount <= 0:
            raise ValidationException(
                "Payment amount must be positive",
                details={"payment_amount": payment_amount}
            )

        if academic_year is None:
            academic_year = self.get_active_academic_year()

        # Scope the charge lookup to the academic year so a payment can only
        # settle the intended year's balance (and to avoid MultipleObjectsReturned
        # when the same fee category is reused across years).
        fee_query = FinanceFee.objects.filter(
            student_id=student_id,
            fee_category_id=fee_category_id,
            tenant=self.tenant,
        )
        if academic_year is not None:
            fee_query = fee_query.filter(academic_year=academic_year)
        student_fee = fee_query.order_by('is_paid', 'created_at').first()

        if student_fee is None:
            raise NotFoundException(
                "No outstanding fee found for student",
                details={
                    "student_id": student_id,
                    "fee_category_id": fee_category_id,
                    "academic_year_id": str(academic_year.id) if academic_year else None,
                }
            )

        if student_fee.balance <= 0:
            raise BusinessLogicException(
                "No outstanding balance for this fee",
                details={"current_balance": student_fee.balance}
            )

        fee_category = student_fee.fee_category
        # Fall back to the charge's own year if the active year was unavailable.
        academic_year = academic_year or student_fee.academic_year
        transaction_category = self._get_or_create_payment_category()
        method = normalize_payment_method(payment_method)
        # A stable grouping key so every FeeTransaction row this payment
        # produces (one per allocated particular) can be reassembled into a
        # single receipt, even if the cashier didn't type one in.
        reference_number = reference_number or self._generate_receipt_reference()

        transaction = self.create_transaction(
            title=f"Fee payment - {fee_category.name}",
            amount=payment_amount,
            category_id=str(transaction_category.id),
            transaction_date=payment_date,
            description=description,
            student_id=student_id,
            academic_year=academic_year,
            payment_method=method,
            reference_number=reference_number,
        )

        # One reference-based duplicate check for the whole submission - done
        # once here since it may now produce several FeeTransaction rows below.
        self._assert_not_duplicate_payment(
            student_fee.student, fee_category, payment_amount, reference_number, academic_year
        )

        # Decrement balance + write FeeTransaction ledger row(s) (single source
        # of truth), split across the category's outstanding particulars so
        # every payment - lump-sum or itemized - is tagged to what it paid for.
        allocations = self._allocate_amount_across_particulars(fee_category, payment_amount)
        for particular, allocated_amount in allocations:
            self._apply_fee_payment_effects(
                student_fee.student, fee_category, allocated_amount, method, payment_date,
                reference=reference_number, academic_year=academic_year,
                fee_particular=particular, skip_duplicate_check=True,
                collected_by=collected_by, notes=description,
            )
        student_fee.refresh_from_db()

        return transaction, student_fee

    def get_student_particular_breakdown(
        self, student_id: str, academic_year: AcademicYear = None
    ) -> List[Dict[str, Any]]:
        """Per-particular due/paid/balance rows for a student's outstanding
        fee charges, for the itemized collect-fee screen.

        For each outstanding FinanceFee, breaks its category down into its
        active FeeParticulars. Payments already tagged with a specific
        ``FeeTransaction.fee_particular`` (new itemized payments) are
        counted directly; older, untagged payments on the same category are
        distributed across its particulars proportionally to their amount,
        since there's no way to know which particular they were originally
        intended to settle.
        """
        today = date.today()
        fees = self.get_student_outstanding_fees(student_id, academic_year).select_related(
            'fee_category', 'batch'
        ).order_by('fee_category__name', 'transaction_date')

        rows = []
        for fee in fees:
            particulars = list(FeeParticular.objects.filter(
                tenant=self.tenant, fee_category=fee.fee_category, is_active=True
            ).select_related('fine_slab', 'applicability_rule').order_by(
                'due_date', 'name'
            ))

            if not particulars:
                continue

            total_particular_amount = sum((p.amount for p in particulars), Decimal('0'))

            untagged_paid = FeeTransaction.objects.filter(
                tenant=self.tenant, student_id=student_id, fee_category=fee.fee_category,
                academic_year=fee.academic_year, transaction_type='payment',
                fee_particular__isnull=True,
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            for particular in particulars:
                tagged_paid = FeeTransaction.objects.filter(
                    tenant=self.tenant, student_id=student_id, fee_particular=particular,
                    academic_year=fee.academic_year, transaction_type='payment',
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

                weight = (
                    (particular.amount / total_particular_amount)
                    if total_particular_amount else Decimal('0')
                )
                proportional_paid = untagged_paid * weight
                paid = tagged_paid + proportional_paid
                balance = max(particular.amount - paid, Decimal('0'))

                rows.append({
                    'finance_fee_id': fee.id,
                    'fee_category_id': fee.fee_category_id,
                    'fee_category_name': fee.fee_category.name,
                    'particular_id': particular.id,
                    'particular_name': particular.name,
                    'due_date': particular.due_date,
                    'amount': particular.amount,
                    'paid': paid,
                    'balance': balance,
                    'is_overdue': bool(
                        particular.due_date and particular.due_date < today and balance > 0
                    ),
                    'applicability_scope': (
                        particular.applicability_rule.rule_type
                        if particular.applicability_rule else 'all'
                    ),
                })
        return rows

    @transaction.atomic
    def process_itemized_fee_payment(
        self,
        student_id: str,
        allocations: List[Dict[str, Any]],
        payment_date: date = None,
        payment_method: str = 'cash',
        academic_year: AcademicYear = None,
        reference_number: str = None,
        collected_by_id: str = None,
        notes: str = None,
    ) -> Dict[str, Any]:
        """Post one payment split across several fee categories/particulars
        in a single atomic submission (Fedena-style itemized collection).

        ``allocations`` is a list of {fee_category_id, particular_id (optional),
        amount} dicts. Every allocation must resolve to the same academic year
        (never allowed to silently span two years for the same student).
        """
        if not allocations:
            raise ValidationException("At least one fee allocation is required")

        if payment_date is None:
            payment_date = date.today()

        student = self._get_student_by_id(student_id)
        collected_by = self._get_employee_by_id(collected_by_id) if collected_by_id else None

        if academic_year is None:
            academic_year = self.get_active_academic_year()

        # A stable grouping key so this submission's FeeTransaction rows can
        # always be reassembled into one receipt, even without a cashier-typed
        # reference.
        reference_number = reference_number or self._generate_receipt_reference()

        # One reference-based duplicate check for the whole submission - a
        # per-line check here would falsely flag the submission's own later
        # lines as duplicates of its earlier ones.
        self._assert_reference_not_reused(student, reference_number)

        method = normalize_payment_method(payment_method)
        results = []
        total_amount = Decimal('0')

        for allocation in allocations:
            amount = Decimal(str(allocation['amount']))
            if amount <= 0:
                raise ValidationException(
                    "Each fee allocation amount must be positive",
                    details={"allocation": allocation},
                )

            fee_category = self._get_fee_category_by_id(allocation['fee_category_id'])

            particular = None
            particular_id = allocation.get('particular_id')
            if particular_id:
                particular = FeeParticular.objects.filter(
                    tenant=self.tenant, id=particular_id, fee_category=fee_category
                ).first()
                if particular is None:
                    raise NotFoundException(
                        "Fee particular not found for this category",
                        details={"particular_id": particular_id},
                    )

            # Confirm the target charge exists for this academic year before
            # touching anything, so a bad allocation fails the whole submission.
            fee_exists = FinanceFee.objects.filter(
                tenant=self.tenant, student=student, fee_category=fee_category,
                academic_year=academic_year,
            ).exists()
            if not fee_exists:
                raise BusinessLogicException(
                    "Cannot record a payment with no matching fee charge for this "
                    "student, category and academic year",
                    details={
                        "fee_category": fee_category.name,
                        "academic_year": str(academic_year) if academic_year else None,
                    },
                )

            student_fee = self._apply_fee_payment_effects(
                student, fee_category, amount, method, payment_date,
                reference=reference_number, academic_year=academic_year,
                fee_particular=particular, skip_duplicate_check=True,
                collected_by=collected_by, notes=notes,
            )
            total_amount += amount
            results.append({
                'fee_category_id': str(fee_category.id),
                'particular_id': str(particular.id) if particular else None,
                'amount': amount,
                'balance': student_fee.balance,
                'is_paid': student_fee.is_paid,
            })

        # One FinanceTransaction for the whole itemized submission (mirrors
        # process_fee_payment's single receipt-capable transaction) so this
        # payment shows up on the fee receipts page / PDF receipt endpoint,
        # same as a lump-sum payment does.
        transaction_category = self._get_or_create_payment_category()
        finance_transaction = self.create_transaction(
            title="Itemized fee payment",
            amount=total_amount,
            category_id=str(transaction_category.id),
            transaction_date=payment_date,
            description=(notes or '').strip() or f"Fee payment via {method} ({len(results)} particular(s))",
            student_id=str(student.id),
            academic_year=academic_year,
            payment_method=method,
            reference_number=reference_number,
        )

        return {
            'student_id': str(student.id),
            'total_amount': total_amount,
            'allocations': results,
            'transaction_id': str(finance_transaction.id),
            'reference_number': reference_number,
        }

    def get_student_outstanding_fees(self, student_id: str, academic_year: AcademicYear = None) -> QuerySet[FinanceFee]:
        qs = FinanceFee.objects.filter(
            student_id=student_id,
            tenant=self.tenant,
            balance__gt=0
        )
        if academic_year is not None:
            qs = qs.filter(academic_year=academic_year)
        return qs

    def get_student_fee_history(self, student_id: str) -> QuerySet[FinanceTransaction]:
        return FinanceTransaction.objects.filter(
            student_id=student_id,
            tenant=self.tenant,
            category__is_income=True
        ).order_by('-transaction_date')
    
    def get_financial_summary(
        self,
        start_date: date = None,
        end_date: date = None,
        academic_year: AcademicYear = None,
    ) -> Dict[str, Any]:
        """Authoritative, year-aware financial summary.

        Consolidates the previously duplicated/overlapping summary methods.
        All filters are optional; pass ``academic_year`` to scope to one year.
        """
        txn_query = Q(tenant=self.tenant)
        if start_date:
            txn_query &= Q(transaction_date__gte=start_date)
        if end_date:
            txn_query &= Q(transaction_date__lte=end_date)
        if academic_year is not None:
            txn_query &= Q(academic_year=academic_year)

        income_total = FinanceTransaction.objects.filter(
            txn_query, category__is_income=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        expense_total = FinanceTransaction.objects.filter(
            txn_query, category__is_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Fee payments are categorised as "Fee Payments" or "Fee Payment - X".
        collected_fees = FinanceTransaction.objects.filter(
            txn_query, student__isnull=False, category__name__startswith="Fee Payment"
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        fee_query = Q(tenant=self.tenant, balance__gt=0)
        if academic_year is not None:
            fee_query &= Q(academic_year=academic_year)
        outstanding_fees = FinanceFee.objects.filter(fee_query).aggregate(
            total=Sum('balance')
        )['total'] or Decimal('0')

        return {
            'total_income': income_total,
            'total_expenses': expense_total,
            'net_profit': income_total - expense_total,
            'collected_fees': collected_fees,
            # `pending_fees` and `outstanding_fees` are kept as aliases so existing
            # dashboard templates that read either key keep working.
            'pending_fees': outstanding_fees,
            'outstanding_fees': outstanding_fees,
            'period_start': start_date,
            'period_end': end_date,
            'academic_year': academic_year,
        }

    def get_fee_collection_report(self, batch_id: str = None, academic_year: AcademicYear = None) -> Dict[str, Any]:
        query = Q(tenant=self.tenant)

        if batch_id:
            query &= Q(student__student_batches__batch_id=batch_id)
        if academic_year is not None:
            query &= Q(academic_year=academic_year)

        total_due = FinanceFee.objects.filter(query).aggregate(
            total=Sum('balance')
        )['total'] or Decimal('0')

        paid_fees_count = FinanceFee.objects.filter(
            query, balance__lte=0
        ).count()

        outstanding_fees_count = FinanceFee.objects.filter(
            query, balance__gt=0
        ).count()

        total_fees_count = paid_fees_count + outstanding_fees_count

        # Amount actually collected (year-scoped), derived from the payment ledger.
        collected_query = Q(tenant=self.tenant, transaction_type='payment')
        if batch_id:
            collected_query &= Q(student__student_batches__batch_id=batch_id)
        if academic_year is not None:
            collected_query &= Q(academic_year=academic_year)
        total_collected = FeeTransaction.objects.filter(collected_query).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        collection_rate = 0
        if total_fees_count > 0:
            collection_rate = (paid_fees_count / total_fees_count) * 100

        return {
            'total_due': total_due,
            'total_collected': total_collected,
            'paid_fees_count': paid_fees_count,
            'outstanding_fees_count': outstanding_fees_count,
            'collection_rate_percentage': round(collection_rate, 2),
            'batch_id': batch_id,
            'academic_year_id': str(academic_year.id) if academic_year else None,
        }

    def find_balance_anomalies(self, academic_year: AcademicYear = None) -> List[Dict[str, Any]]:
        """Detect concrete fee-ledger integrity violations for the tenant.

        Reports rows whose stored state cannot be trusted:
        - negative balance (overpayment recorded against a charge)
        - is_paid flag inconsistent with the balance
        - payments with no matching FinanceFee charge (orphans) for a
          (student, fee_category, academic_year) group

        Returns a list of anomaly dicts; an empty list means no drift detected.
        """
        anomalies: List[Dict[str, Any]] = []

        fee_q = Q(tenant=self.tenant)
        if academic_year is not None:
            fee_q &= Q(academic_year=academic_year)

        for fee in FinanceFee.objects.filter(fee_q).select_related('student', 'fee_category', 'academic_year'):
            if fee.balance < 0:
                anomalies.append({
                    'type': 'negative_balance', 'finance_fee_id': str(fee.id),
                    'student_id': str(fee.student_id), 'balance': str(fee.balance),
                    'academic_year_id': str(fee.academic_year_id) if fee.academic_year_id else None,
                })
            if fee.is_paid and fee.balance > 0:
                anomalies.append({
                    'type': 'paid_flag_but_outstanding', 'finance_fee_id': str(fee.id),
                    'student_id': str(fee.student_id), 'balance': str(fee.balance),
                })
            if not fee.is_paid and fee.balance <= 0:
                anomalies.append({
                    'type': 'unpaid_flag_but_settled', 'finance_fee_id': str(fee.id),
                    'student_id': str(fee.student_id), 'balance': str(fee.balance),
                })

        # Orphan payments: a payment ledger row whose (student, category, year)
        # has no FinanceFee charge at all.
        pay_q = Q(tenant=self.tenant, transaction_type='payment')
        if academic_year is not None:
            pay_q &= Q(academic_year=academic_year)
        for pay in FeeTransaction.objects.filter(pay_q).select_related('student', 'fee_category'):
            charge_exists = FinanceFee.objects.filter(
                tenant=self.tenant, student_id=pay.student_id,
                fee_category_id=pay.fee_category_id,
                academic_year_id=pay.academic_year_id,
            ).exists()
            if not charge_exists:
                anomalies.append({
                    'type': 'orphan_payment', 'fee_transaction_id': str(pay.id),
                    'student_id': str(pay.student_id), 'amount': str(pay.amount),
                    'academic_year_id': str(pay.academic_year_id) if pay.academic_year_id else None,
                })

        return anomalies


    def _get_transaction_category_by_id(self, category_id: str) -> FinanceTransactionCategory:
        try:
            return FinanceTransactionCategory.objects.get(
                id=category_id,
                tenant=self.tenant
            )
        except FinanceTransactionCategory.DoesNotExist:
            raise NotFoundException(
                f"Transaction category with id {category_id} not found",
                details={"category_id": category_id}
            )
    
    def _get_fee_category_by_id(self, fee_category_id: str) -> FeeCategory:
        try:
            return FeeCategory.objects.get(
                id=fee_category_id,
                tenant=self.tenant,
                is_deleted=False
            )
        except FeeCategory.DoesNotExist:
            raise NotFoundException(
                f"Fee category with id {fee_category_id} not found",
                details={"fee_category_id": fee_category_id}
            )
    
    def _get_student_by_id(self, student_id: str) -> Student:
        try:
            return Student.objects.get(
                id=student_id,
                tenant=self.tenant,
                is_active=True
            )
        except Student.DoesNotExist:
            raise NotFoundException(
                f"Student with id {student_id} not found",
                details={"student_id": student_id}
            )
    
    def _get_employee_by_id(self, employee_id: str) -> Employee:
        try:
            return Employee.objects.get(
                id=employee_id,
                tenant=self.tenant,
                status=True
            )
        except Employee.DoesNotExist:
            raise NotFoundException(
                f"Employee with id {employee_id} not found",
                details={"employee_id": employee_id}
            )
    
    def _get_batch_by_id(self, batch_id: str) -> Batch:
        try:
            return Batch.objects.get(
                id=batch_id,
                tenant=self.tenant,
                is_deleted=False
            )
        except Batch.DoesNotExist:
            raise NotFoundException(
                f"Batch with id {batch_id} not found",
                details={"batch_id": batch_id}
            )
    
    def _get_or_create_payment_category(self) -> FinanceTransactionCategory:
        category, created = FinanceTransactionCategory.objects.get_or_create(
            name="Fee Payments",
            tenant=self.tenant,
            defaults={
                "description": "Student fee payments",
                "is_income": True
            }
        )
        return category
    
    def _validate_create_data(self, data: Dict[str, Any]) -> None:
        super()._validate_create_data(data)
        
        required_fields = ['title', 'amount', 'category']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationException(
                    f"Required field '{field}' is missing or empty",
                    details={"field": field}
                )
        
        amount = data.get('amount')
        if amount is not None and amount <= 0:
            raise ValidationException(
                "Transaction amount must be positive",
                details={"amount": amount}
            )
    
    def get_student_fee_balance(self, student_id: str, academic_year: AcademicYear = None) -> Decimal:
        """Get the total fee balance for a student (optionally scoped to a year)."""
        qs = FinanceFee.objects.filter(
            student_id=student_id,
            tenant=self.tenant
        )
        if academic_year is not None:
            qs = qs.filter(academic_year=academic_year)
        return qs.aggregate(total=Sum('balance'))['total'] or Decimal('0')
    
    def get_financial_overview(self) -> Dict[str, Any]:
        """Get financial overview statistics"""
        income_total = self.get_base_queryset().filter(
            category__is_income=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        expense_total = self.get_base_queryset().filter(
            category__is_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        outstanding_fees = FinanceFee.objects.filter(
            tenant=self.tenant
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0')
        
        return {
            "total_income": float(income_total),
            "total_expenses": float(expense_total),
            "net_income": float(income_total - expense_total),
            "outstanding_fees": float(outstanding_fees),
            "recent_transactions": list(
                self.get_base_queryset()
                .order_by('-transaction_date')[:10]
                .values('title', 'amount', 'transaction_date', 'category__name')
            )
        }

    def get_transaction_summary(self) -> Dict[str, Any]:
        """Get transaction summary for dashboard"""
        queryset = self.get_base_queryset()
        
        # Calculate income and expenses
        income_total = queryset.filter(
            category__is_income=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        expense_total = queryset.filter(
            category__is_income=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        transaction_count = queryset.count()
        
        return {
            'total_income': income_total,
            'total_expenses': expense_total,
            'net_balance': income_total - expense_total,
            'transaction_count': transaction_count
        }

    def get_recent_transactions(self, limit: int = 20) -> QuerySet:
        return self.get_base_queryset().select_related('category').order_by('-created_at')[:limit]

    @transaction.atomic
    def create_fee_payment(self, student, amount, payment_method, fee_category, payment_date=None, academic_year=None, **kwargs):
        if payment_date is None:
            payment_date = date.today()

        method = normalize_payment_method(payment_method)
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if academic_year is None:
            academic_year = fee_category.academic_year or self.get_active_academic_year()

        fee_category_obj, created = FinanceTransactionCategory.objects.get_or_create(
            tenant=self.tenant,
            name=f"Fee Payment - {fee_category.name}",
            defaults={'is_income': True, 'description': f'Fee payments for {fee_category.name}'}
        )

        kwargs.pop('payment_method', None)  # avoid duplicate kwarg
        txn = self.create_transaction(
            title=f"Fee Payment - {student.first_name} {student.last_name}",
            amount=amount,
            category_id=str(fee_category_obj.id),
            transaction_date=payment_date,
            description=f"Fee payment for {fee_category.name} via {method}",
            student_id=str(student.id),
            academic_year=academic_year,
            payment_method=method,
            **kwargs
        )

        # Decrement the student's outstanding balance + write the FeeTransaction ledger row
        self._apply_fee_payment_effects(
            student, fee_category, amount, method, payment_date,
            reference=getattr(txn, 'reference_number', None),
            academic_year=academic_year,
        )

        return txn

    # ------------------------------------------------------------------
    # Phase 3 — discounts, scholarships (waivers), and late fines.
    # Each adjusts the matching year's FinanceFee balance AND writes a
    # year-stamped FeeTransaction ledger row, never a silent balance edit.
    # ------------------------------------------------------------------

    def _get_year_scoped_fee(self, student, fee_category, academic_year):
        """Return the matching FinanceFee charge for a student/category/year."""
        q = FinanceFee.objects.filter(
            student=student, fee_category=fee_category, tenant=self.tenant
        )
        if academic_year is not None:
            q = q.filter(academic_year=academic_year)
        return q.order_by('is_paid', 'created_at').first()

    @transaction.atomic
    def apply_discount(self, student, fee_category, discount: FeeDiscount,
                       base_amount: Decimal = None, academic_year: AcademicYear = None):
        """Apply a FeeDiscount to a student's charge for the given year.

        Reduces the matching FinanceFee balance and records a year-stamped
        FeeTransaction(transaction_type='discount'). Returns (fee, discount_amount).
        """
        if academic_year is None:
            academic_year = fee_category.academic_year or self.get_active_academic_year()

        fee = self._get_year_scoped_fee(student, fee_category, academic_year)
        if fee is None:
            raise BusinessLogicException(
                "No fee charge to discount for this student/category/year",
                details={"fee_category": fee_category.name},
            )

        if base_amount is None:
            base_amount = fee.balance
        discount_amount = Decimal(str(discount.calculate_discount(base_amount)))
        discount_amount = min(discount_amount, fee.balance)
        if discount_amount <= 0:
            return fee, Decimal('0.00')

        fee.balance -= discount_amount
        fee.discount_amount = (fee.discount_amount or Decimal('0')) + discount_amount
        if fee.balance <= 0:
            fee.balance = Decimal('0.00')
            fee.is_paid = True
        fee.save()

        ledger_row = FeeTransaction.objects.create(
            tenant=self.tenant, student=student, fee_category=fee_category,
            academic_year=academic_year, transaction_type='discount',
            amount=discount_amount, discount=discount,
            description=f"Discount applied: {discount.name}",
        )
        self._log_ledger_event('discount', ledger_row, student, academic_year,
                               extra={'discount': discount.name})
        InvoiceService(self.tenant).mark_invoice_paid_if_settled(fee)
        self._enqueue_qb_invoice_resync(fee)
        return fee, discount_amount

    @transaction.atomic
    def apply_fine(self, student, fee_category, fine_slab: FineSlab,
                   academic_year: AcademicYear = None, days_overdue: int = None):
        """Apply a late FineSlab to a student's outstanding charge for the year.

        Increases the matching FinanceFee balance and records a year-stamped
        FeeTransaction(transaction_type='fine'). Idempotent per
        (student, category, year, fine_slab). Returns (fee, fine_amount).
        """
        if academic_year is None:
            academic_year = fee_category.academic_year or self.get_active_academic_year()

        fee = self._get_year_scoped_fee(student, fee_category, academic_year)
        if fee is None or fee.balance <= 0:
            return fee, Decimal('0.00')

        # Idempotency: do not stack the same fine twice for the same year.
        already = FeeTransaction.objects.filter(
            tenant=self.tenant, student=student, fee_category=fee_category,
            academic_year=academic_year, transaction_type='fine', fine_slab=fine_slab,
        ).exists()
        if already:
            return fee, Decimal('0.00')

        fine_amount = Decimal(str(fine_slab.calculate_fine(fee.balance)))
        if fine_amount <= 0:
            return fee, Decimal('0.00')

        fee.balance += fine_amount
        fee.is_paid = False
        fee.save()

        note = f"Fine: {fine_slab.fine_name}"
        if days_overdue is not None:
            note += f" ({days_overdue} days overdue)"
        ledger_row = FeeTransaction.objects.create(
            tenant=self.tenant, student=student, fee_category=fee_category,
            academic_year=academic_year, transaction_type='fine',
            amount=fine_amount, fine_slab=fine_slab, description=note,
        )
        self._log_ledger_event('fine', ledger_row, student, academic_year,
                               extra={'fine_slab': fine_slab.fine_name})
        InvoiceService(self.tenant).mark_invoice_paid_if_settled(fee)
        self._enqueue_qb_invoice_resync(fee)
        return fee, fine_amount

    @transaction.atomic
    def grant_waiver(self, student, fee_category, waiver_type: str,
                     academic_year: AcademicYear = None, amount: Decimal = None,
                     percentage: Decimal = None, reason: str = "",
                     approved_by: Employee = None):
        """Grant a scholarship/waiver: create a FeeWaiver record AND reduce the
        matching year's FinanceFee balance via a year-stamped discount ledger row.
        Returns (waiver, fee, waiver_amount).
        """
        if academic_year is None:
            academic_year = fee_category.academic_year or self.get_active_academic_year()
        if academic_year is None:
            raise ValidationException("An academic year is required to grant a waiver")

        fee = self._get_year_scoped_fee(student, fee_category, academic_year)
        if fee is None:
            raise BusinessLogicException(
                "No fee charge to waive for this student/category/year",
                details={"fee_category": fee_category.name},
            )

        if percentage is not None:
            waiver_amount = (fee.balance * Decimal(str(percentage))) / Decimal('100')
        elif amount is not None:
            waiver_amount = Decimal(str(amount))
        else:
            raise ValidationException("Provide either amount or percentage for the waiver")
        waiver_amount = min(waiver_amount, fee.balance)
        if waiver_amount <= 0:
            raise BusinessLogicException("Waiver amount must be positive and within the outstanding balance")

        waiver = FeeWaiver.objects.create(
            tenant=self.tenant, student=student, fee_category=fee_category,
            academic_year=academic_year, waiver_type=waiver_type,
            amount=waiver_amount, percentage=percentage, reason=reason or waiver_type,
            approved_by=approved_by, approval_date=date.today(), is_active=True,
        )

        fee.balance -= waiver_amount
        fee.discount_amount = (fee.discount_amount or Decimal('0')) + waiver_amount
        if fee.balance <= 0:
            fee.balance = Decimal('0.00')
            fee.is_paid = True
        fee.save()

        ledger_row = FeeTransaction.objects.create(
            tenant=self.tenant, student=student, fee_category=fee_category,
            academic_year=academic_year, transaction_type='discount',
            amount=waiver_amount,
            description=f"{waiver_type} waiver: {reason}" if reason else f"{waiver_type} waiver",
        )
        self._log_ledger_event('waiver', ledger_row, student, academic_year,
                               extra={'waiver_type': waiver_type, 'waiver_id': str(waiver.id)},
                               user=approved_by)
        InvoiceService(self.tenant).mark_invoice_paid_if_settled(fee)
        self._enqueue_qb_invoice_resync(fee)
        return waiver, fee, waiver_amount

    @transaction.atomic
    def revoke_waiver(self, waiver_id: str, reason: str = "", user=None) -> Tuple[FeeWaiver, FinanceFee]:
        """Revoke a previously granted waiver: restore the waived amount to
        the matching charge's balance and post a compensating ``adjustment``
        ledger row. Mirrors ``reverse_payment``'s compensating-entry
        philosophy - nothing is deleted, history is fully auditable.

        Idempotent: a waiver already revoked cannot be revoked again.
        """
        try:
            waiver = FeeWaiver.objects.get(id=waiver_id, tenant=self.tenant)
        except FeeWaiver.DoesNotExist:
            raise NotFoundException(
                "Waiver not found", details={"waiver_id": waiver_id},
            )

        if not waiver.is_active:
            raise BusinessLogicException(
                "This waiver has already been revoked",
                details={"waiver_id": waiver_id},
            )

        fee = self._get_year_scoped_fee(waiver.student, waiver.fee_category, waiver.academic_year)
        if fee is None:
            raise BusinessLogicException(
                "No matching fee charge found to restore the waived amount to",
                details={"fee_category": waiver.fee_category.name},
            )

        fee.balance += waiver.amount
        fee.discount_amount = max((fee.discount_amount or Decimal('0')) - waiver.amount, Decimal('0'))
        if fee.balance > 0:
            fee.is_paid = False
        fee.save()

        waiver.is_active = False
        waiver.revoked_by = user
        waiver.revoked_at = timezone.now()
        waiver.revocation_reason = reason
        waiver.save(update_fields=['is_active', 'revoked_by', 'revoked_at', 'revocation_reason'])

        ledger_row = FeeTransaction.objects.create(
            tenant=self.tenant, student=waiver.student, fee_category=waiver.fee_category,
            academic_year=waiver.academic_year, transaction_type='adjustment',
            amount=waiver.amount,
            description=f"Waiver revoked: {reason}" if reason else "Waiver revoked",
        )
        self._log_ledger_event('waiver_revoked', ledger_row, waiver.student, waiver.academic_year,
                               extra={'waiver_id': str(waiver.id)}, user=user)

        # Reinstate the charge on the guardian's consolidated invoice.
        InvoiceService(self.tenant).upsert_guardian_invoice(fee)
        self._enqueue_qb_invoice_resync(fee)

        return waiver, fee

    def accrue_late_fines(self, fine_slab: FineSlab, fee_category: FeeCategory,
                          due_date: date, academic_year: AcademicYear = None,
                          reference_date: date = None) -> Dict[str, Any]:
        """Apply ``fine_slab`` to every overdue, unpaid charge in ``fee_category``.

        If a fee belongs to a collection with a late_fee_rule set, that rule takes
        precedence (overrides the passed fine_slab — no stacking). Otherwise uses
        the passed fine_slab.

        Used by the ``accrue_late_fines`` management command (Celery-beat-able).
        Returns a summary dict. Idempotent via apply_fine.
        """
        if reference_date is None:
            reference_date = date.today()
        if academic_year is None:
            academic_year = fee_category.academic_year or self.get_active_academic_year()

        days_overdue = (reference_date - due_date).days
        applied = 0
        total_fines = Decimal('0.00')
        if days_overdue < fine_slab.days_after_due:
            return {"applied": 0, "total_fines": total_fines, "days_overdue": days_overdue}

        fees = FinanceFee.objects.filter(
            tenant=self.tenant, fee_category=fee_category,
            is_paid=False, balance__gt=0,
        ).select_related('student', 'fee_collection')

        if academic_year is not None:
            fees = fees.filter(academic_year=academic_year)

        for fee in fees:
            # Determine which fine rule to apply:
            # If the fee's collection has a late_fee_rule, it takes precedence (no stacking)
            # Otherwise use the passed fine_slab
            effective_rule = fine_slab
            if fee.fee_collection and fee.fee_collection.late_fee_rule:
                effective_rule = fee.fee_collection.late_fee_rule

            _, amount = self.apply_fine(
                fee.student, fee_category, effective_rule,
                academic_year=academic_year, days_overdue=days_overdue,
            )
            if amount > 0:
                applied += 1
                total_fines += amount

        return {"applied": applied, "total_fines": total_fines, "days_overdue": days_overdue}

    # ------------------------------------------------------------------
    # Phase 6 — payment reversal (compensating entry, never a delete/edit).
    # ------------------------------------------------------------------
    @transaction.atomic
    def reverse_payment(self, fee_transaction_id: str, reason: str = "", user=None) -> FeeTransaction:
        """Reverse a recorded payment by posting a compensating refund ledger row
        and an offsetting (expense) FinanceTransaction, restoring the charge
        balance. History is preserved — nothing is deleted or edited.

        Idempotent: a payment already reversed cannot be reversed again.
        """
        try:
            original = FeeTransaction.objects.get(
                id=fee_transaction_id, tenant=self.tenant, transaction_type='payment',
            )
        except FeeTransaction.DoesNotExist:
            raise NotFoundException(
                "Payment to reverse not found",
                details={"fee_transaction_id": fee_transaction_id},
            )

        reversal_ref = f"REVERSAL:{original.id}"
        if FeeTransaction.objects.filter(
            tenant=self.tenant, transaction_type='refund', reference_number=reversal_ref,
        ).exists():
            raise BusinessLogicException(
                "This payment has already been reversed",
                details={"fee_transaction_id": fee_transaction_id},
            )

        academic_year = original.academic_year
        # Restore the outstanding balance on the matching charge.
        fee = self._get_year_scoped_fee(original.student, original.fee_category, academic_year)
        if fee is not None:
            fee.balance += original.amount
            fee.is_paid = False
            fee.save()
            student = original.student
            if getattr(student, 'has_paid_fees', False):
                student.has_paid_fees = False
                student.save(update_fields=['has_paid_fees'])

        refund_row = FeeTransaction.objects.create(
            tenant=self.tenant, student=original.student, fee_category=original.fee_category,
            academic_year=academic_year, transaction_type='refund',
            amount=original.amount, reference_number=reversal_ref,
            description=f"Reversal of payment {original.id}" + (f": {reason}" if reason else ""),
        )

        # Offsetting accounting entry (expense) so income summaries stay correct.
        refund_category, _ = FinanceTransactionCategory.objects.get_or_create(
            tenant=self.tenant, name="Fee Refunds",
            defaults={"is_income": False, "description": "Reversed/refunded fee payments"},
        )
        self.create_transaction(
            title=f"Fee refund - {original.fee_category.name if original.fee_category else 'payment'}",
            amount=original.amount,
            category_id=str(refund_category.id),
            student_id=str(original.student_id),
            academic_year=academic_year,
            description=f"Reversal of payment {original.id}" + (f": {reason}" if reason else ""),
            user=user,
        )

        self._log_ledger_event('payment_reversal', refund_row, original.student, academic_year,
                               user=user, extra={'reversed_payment_id': str(original.id), 'reason': reason})
        if fee is not None:
            InvoiceService(self.tenant).mark_invoice_paid_if_settled(fee)
            self._enqueue_qb_invoice_resync(fee)
        return refund_row

    @transaction.atomic
    def remove_student_charge(self, fee_transaction_id: str, reason: str = "", user=None) -> None:
        """Undo a one-time particular charge added via AddStudentParticularView.

        Unlike ``reverse_payment``/``revoke_waiver``, this is a genuine delete
        rather than a compensating entry: it's only allowed while the charge
        is still exactly as it was created (no payment, discount, or fine has
        touched it, and it isn't a billing-run charge with a fee_collection),
        so no money has actually moved against it yet - there is nothing to
        preserve a paper trail for. Deleting the FinanceFee cascades to its
        (also-untouched) guardian invoice line; the guardian's invoice totals
        are then recomputed.
        """
        try:
            original = FeeTransaction.objects.get(
                id=fee_transaction_id, tenant=self.tenant, transaction_type='charge',
            )
        except FeeTransaction.DoesNotExist:
            raise NotFoundException(
                "Charge not found", details={"fee_transaction_id": fee_transaction_id},
            )

        reference = original.reference_number or ""
        if not reference.startswith("CHARGE:"):
            raise BusinessLogicException("This charge cannot be removed")

        finance_fee_id = reference.split(":", 1)[1]
        fee = FinanceFee.objects.filter(id=finance_fee_id, tenant=self.tenant).first()
        if fee is None:
            raise BusinessLogicException("This charge has already been removed")

        if fee.fee_collection_id is not None:
            raise BusinessLogicException("Only one-time added charges can be removed this way")
        if fee.balance != original.amount:
            raise BusinessLogicException(
                "This charge has already been paid, discounted, or fined against, "
                "and can no longer be removed"
            )

        invoice_line = FamilyInvoiceLine.objects.filter(
            tenant=self.tenant, finance_fee=fee
        ).select_related('invoice').first()
        invoice = invoice_line.invoice if invoice_line else None

        fee.delete()
        original.delete()

        if invoice is not None:
            InvoiceService(self.tenant).recompute_totals(invoice)
            self._enqueue_qb_sync('invoice_resync', invoice.id)

        self.logger.log_delete(
            resource_type='fee_charge', resource_id=str(finance_fee_id), user=user,
        )

    def create_master_particular(self, name, description=None, is_active=True):
        """Create a master particular template — reusable across categories"""
        from core.models import FeeMasterParticular

        master = FeeMasterParticular.objects.create(
            tenant=self.tenant,
            name=name,
            description=description,
            is_active=is_active,
        )
        return master

    def create_master_discount(self, name, discount_type, value, description=None, is_active=True):
        """Create a master discount template — reusable across categories"""
        from core.models import FeeMasterDiscount

        master = FeeMasterDiscount.objects.create(
            tenant=self.tenant,
            name=name,
            discount_type=discount_type,
            value=value,
            description=description,
            is_active=is_active,
        )
        return master

    def list_master_particulars(self, is_active=True):
        """List master particular templates"""
        from core.models import FeeMasterParticular

        qs = FeeMasterParticular.objects.filter(tenant=self.tenant)
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        return qs.order_by('name')

    def list_master_discounts(self, is_active=True):
        """List master discount templates"""
        from core.models import FeeMasterDiscount

        qs = FeeMasterDiscount.objects.filter(tenant=self.tenant)
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        return qs.order_by('name')

    def update_master_particular(self, master_id, **fields):
        """Update a master particular. Raises NotFoundException if not found, DuplicateException if name collides."""
        try:
            master = self.get_base_queryset(FeeMasterParticular).get(id=master_id)
        except FeeMasterParticular.DoesNotExist:
            raise NotFoundException(f"Master particular with id {master_id} not found")

        if 'name' in fields:
            # Check for name uniqueness within tenant
            name = fields['name']
            if self.get_base_queryset(FeeMasterParticular).filter(name=name).exclude(id=master_id).exists():
                raise DuplicateException(f"Master particular name '{name}' already exists for this tenant")

        for key, value in fields.items():
            setattr(master, key, value)
        master.save()
        return master

    def delete_master_particular(self, master_id):
        """Delete a master particular. Raises NotFoundException if not found."""
        try:
            master = self.get_base_queryset(FeeMasterParticular).get(id=master_id)
        except FeeMasterParticular.DoesNotExist:
            raise NotFoundException(f"Master particular with id {master_id} not found")
        master.delete()

    def update_master_discount(self, master_id, **fields):
        """Update a master discount. Raises NotFoundException if not found, DuplicateException if name collides."""
        try:
            master = self.get_base_queryset(FeeMasterDiscount).get(id=master_id)
        except FeeMasterDiscount.DoesNotExist:
            raise NotFoundException(f"Master discount with id {master_id} not found")

        if 'name' in fields:
            # Check for name uniqueness within tenant
            name = fields['name']
            if self.get_base_queryset(FeeMasterDiscount).filter(name=name).exclude(id=master_id).exists():
                raise DuplicateException(f"Master discount name '{name}' already exists for this tenant")

        for key, value in fields.items():
            setattr(master, key, value)
        master.save()
        return master

    def delete_master_discount(self, master_id):
        """Delete a master discount. Raises NotFoundException if not found."""
        try:
            master = self.get_base_queryset(FeeMasterDiscount).get(id=master_id)
        except FeeMasterDiscount.DoesNotExist:
            raise NotFoundException(f"Master discount with id {master_id} not found")
        master.delete()

    def create_applicability_rule(self, rule_type, **fields):
        """Create an applicability rule. Validates required fields per rule_type.

        rule_type choices: 'all', 'admission_number', 'student_category', 'batch', 'individual_student'
        fields depend on rule_type:
          - 'all': no extra fields required
          - 'admission_number': admission_number (str)
          - 'student_category': student_category_id (UUID)
          - 'batch': batch_id (UUID)
          - 'individual_student': student_id (UUID)
        """
        if rule_type not in ['all', 'admission_number', 'student_category', 'batch', 'individual_student']:
            raise ValidationException(f"Invalid rule_type: {rule_type}")

        if rule_type == 'admission_number' and not fields.get('admission_number'):
            raise ValidationException("admission_number is required for admission_number rule_type")
        elif rule_type == 'student_category' and not fields.get('student_category_id'):
            raise ValidationException("student_category_id is required for student_category rule_type")
        elif rule_type == 'batch' and not fields.get('batch_id'):
            raise ValidationException("batch_id is required for batch rule_type")
        elif rule_type == 'individual_student' and not fields.get('student_id'):
            raise ValidationException("student_id is required for individual_student rule_type")

        rule = FeeApplicabilityRule.objects.create(
            tenant=self.tenant,
            rule_type=rule_type,
            **fields
        )
        return rule

    def list_applicability_rules(self, is_active=None):
        """List applicability rules, optionally filtered by active status."""
        qs = FeeApplicabilityRule.objects.filter(tenant=self.tenant).select_related(
            'student_category', 'batch', 'student'
        )
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        return qs.order_by('rule_type', 'created_at')

    def update_applicability_rule(self, rule_id, **fields):
        """Update an applicability rule. Raises NotFoundException if not found."""
        try:
            rule = self.get_base_queryset(FeeApplicabilityRule).get(id=rule_id)
        except FeeApplicabilityRule.DoesNotExist:
            raise NotFoundException(f"Applicability rule with id {rule_id} not found")

        for key, value in fields.items():
            setattr(rule, key, value)
        rule.save()
        return rule

    def delete_applicability_rule(self, rule_id):
        """Delete an applicability rule. Raises NotFoundException if not found."""
        try:
            rule = self.get_base_queryset(FeeApplicabilityRule).get(id=rule_id)
        except FeeApplicabilityRule.DoesNotExist:
            raise NotFoundException(f"Applicability rule with id {rule_id} not found")
        rule.delete()