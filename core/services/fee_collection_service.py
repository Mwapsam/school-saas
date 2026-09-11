"""Fee collections: a named billing period (e.g. "Term 1 Collection") for a
fee category + batch. Creating one materialises a FinanceFee obligation per
active student in the batch, priced per-student from the category's active
particulars that actually apply to them (applicability_rule + effective/
expiry dates - see fee_particulars.applicable_particulars_for_student) -
students in the same batch can therefore owe different amounts and get
different FinanceFeeItem snapshots. Re-running is idempotent.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import (
    Count, DecimalField, Exists, F, IntegerField, OuterRef, Q, QuerySet,
    Subquery, Sum,
)
from django.db.models.functions import Coalesce

from core.models import (
    AcademicYear, Batch, BatchFeeCategory, BatchStudent, FeeCategory,
    FeeCollection, FeeCollectionParticular, FeeMasterParticular, FeeParticular,
    FineSlab, FinanceFee, FinanceFeeItem, Term,
)
from .base import TenantAwareService
from .exceptions import NotFoundException, ValidationException
from .fee_particulars import applicable_particulars_for_student
from .invoice_service import InvoiceService
from .logging_service import ServiceLogger, logged_operation
from .qb_sync_helpers import enqueue_qb_sync


class FeeCollectionService(TenantAwareService[FeeCollection]):
    def __init__(self, tenant):
        super().__init__(FeeCollection, tenant)
        self.logger = ServiceLogger('fee_collection', tenant)

    def get_active_academic_year(self) -> Optional[AcademicYear]:
        return AcademicYear.objects.filter(
            tenant=self.tenant, is_active=True
        ).first()

    def resolve_term_for_batch(self, batch: Batch, term_name: str) -> Optional[Term]:
        """Phase 3: Terms are year-scoped (not per-batch). Resolve to the term
        for this batch's academic year by name."""
        return Term.objects.filter(
            tenant=self.tenant, academic_year=batch.academic_year, name=term_name
        ).first()

    def _price_for_student(self, fee_category: FeeCategory, student) -> tuple:
        """Total charge for `student` under `fee_category`, and the list of
        FeeParticular rows that produced it - only particulars that actually
        apply to this student (applicability_rule.matches(student), within
        their effective/expiry window). Two students in the same category
        can therefore owe different amounts and get different line items.
        """
        has_any_particular = FeeParticular.objects.filter(
            tenant=self.tenant, fee_category=fee_category, is_active=True
        ).exists()
        if not has_any_particular:
            raise ValidationException(
                f"'{fee_category.name}' has no active particulars. "
                f"Add particulars in Fee Structure before generating a collection."
            )
        applicable = applicable_particulars_for_student(fee_category, student)
        total = sum((p.amount for p in applicable), Decimal('0.00'))
        return total, applicable

    def _collection_particular_lines(self, collection, student) -> list:
        """Active per-collection extra particulars (e.g. PTA) that apply to this
        student. These are unioned on top of the fee category's particulars when
        pricing, and belong to just this one collection."""
        if collection is None:
            return []
        out = []
        for fcp in collection.extra_particulars.filter(
            is_active=True
        ).select_related('applicability_rule'):
            if fcp.applicability_rule and not fcp.applicability_rule.matches(student):
                continue
            out.append(fcp)
        return out

    @logged_operation('create_fee_collection')
    def create_collection(
        self,
        name: str,
        fee_category_id: str,
        batch_ids: List[str],
        due_date,
        start_date,
        end_date,
        academic_year: Optional[AcademicYear] = None,
        term_name: Optional[str] = None,
        frequency: str = 'one_time',
        late_fee_rule_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not name or not name.strip():
            raise ValidationException("Collection name is required")
        if not batch_ids:
            raise ValidationException("Select at least one batch")
        if frequency not in ['one_time', 'monthly', 'termly', 'yearly']:
            raise ValidationException(f"Invalid frequency: {frequency}")

        fee_category = FeeCategory.objects.filter(
            tenant=self.tenant, id=fee_category_id, is_deleted=False
        ).first()
        if not fee_category:
            raise NotFoundException(f"Fee category {fee_category_id} not found")

        academic_year = academic_year or fee_category.academic_year \
            or self.get_active_academic_year()

        # Validate late_fee_rule if provided
        late_fee_rule = None
        if late_fee_rule_id:
            from core.models import FineSlab
            late_fee_rule = FineSlab.objects.filter(
                tenant=self.tenant, id=late_fee_rule_id
            ).first()
            if not late_fee_rule:
                raise NotFoundException(f"Fine slab {late_fee_rule_id} not found")

        collections: List[FeeCollection] = []
        created = 0
        skipped = 0

        # Calculate next_generation_date for recurring collections
        next_generation_date = None
        if frequency != 'one_time':
            from datetime import date, timedelta
            from dateutil.relativedelta import relativedelta
            today = date.today()
            if frequency == 'monthly':
                next_generation_date = today + relativedelta(months=1)
            elif frequency == 'termly':
                next_generation_date = today + relativedelta(months=3)
            elif frequency == 'yearly':
                next_generation_date = today + relativedelta(years=1)

        with transaction.atomic():
            for batch_id in batch_ids:
                batch = Batch.objects.filter(
                    tenant=self.tenant, id=batch_id, is_deleted=False
                ).first()
                if not batch:
                    raise NotFoundException(f"Batch {batch_id} not found")

                term = self.resolve_term_for_batch(batch, term_name) if term_name else None

                collection, _ = FeeCollection.objects.get_or_create(
                    tenant=self.tenant,
                    name=name.strip(),
                    fee_category=fee_category,
                    batch=batch,
                    term=term,
                    defaults={
                        'start_date': start_date,
                        'end_date': end_date,
                        'due_date': due_date,
                        'academic_year': academic_year,
                        'is_active': True,
                        'frequency': frequency,
                        'late_fee_rule': late_fee_rule,
                        'next_generation_date': next_generation_date,
                    },
                )
                collections.append(collection)

                students = [
                    bs.student for bs in BatchStudent.objects.filter(
                        tenant=self.tenant, batch=batch, is_active=True
                    ).select_related('student')
                ]

                # Scoped to (fee_category, academic_year), not to this one
                # collection - a student already charged under a sibling
                # collection for the same category/year (e.g. a re-run under
                # a different name) must not be charged again.
                existing = set(
                    FinanceFee.objects.filter(
                        tenant=self.tenant, fee_category=fee_category,
                        academic_year=academic_year,
                    ).values_list('student_id', flat=True)
                )

                for student in students:
                    if student.id in existing:
                        skipped += 1
                        continue
                    amount, applicable = self._price_for_student(fee_category, student)
                    extras = self._collection_particular_lines(collection, student)
                    if not applicable and not extras:
                        # Every particular in this category is scoped away
                        # from this student (e.g. admission-specific fees) -
                        # nothing to charge them under this collection.
                        skipped += 1
                        continue
                    extra_total = sum((e.amount for e in extras), Decimal('0.00'))
                    total = amount + extra_total
                    finance_fee = FinanceFee.objects.create(
                        tenant=self.tenant,
                        fee_category=fee_category,
                        fee_collection=collection,
                        student=student,
                        batch=batch,
                        academic_year=academic_year,
                        balance=total,
                        particular_total=total,
                        transaction_date=due_date,
                        is_paid=False,
                    )
                    FinanceFeeItem.objects.bulk_create([
                        FinanceFeeItem(
                            tenant=self.tenant, finance_fee=finance_fee,
                            fee_particular=p, particular_name=p.name, amount=p.amount,
                        )
                        for p in applicable
                    ] + [
                        FinanceFeeItem(
                            tenant=self.tenant, finance_fee=finance_fee,
                            fee_particular=None, particular_name=e.name, amount=e.amount,
                        )
                        for e in extras
                    ])
                    created += 1

        return {
            'collections': collections,
            'obligations_created': created,
            'students_skipped': skipped,
        }

    def sync_student_enrollment(self, batch: Batch, student) -> int:
        """Top up FinanceFee obligations for a student newly (re-)enrolled in
        `batch`, against every still-open collection already running for it.
        """
        open_collections = FeeCollection.objects.filter(
            tenant=self.tenant, batch=batch, is_active=True,
            status__in=['draft', 'published'],
        )
        created = 0
        for collection in open_collections:
            # Check if this collection's (fee_category, batch) has scoped
            # students via BatchFeeCategoryStudent. If scoped (non-empty
            # relation) and the student isn't in it, skip this collection.
            bfc = BatchFeeCategory.objects.filter(
                tenant=self.tenant, fee_category=collection.fee_category, batch=batch
            ).first()
            if bfc and bfc.scoped_students.exists():
                if not bfc.scoped_students.filter(student=student).exists():
                    continue

            # Same cross-collection scoping as create_collection() - a
            # student already charged for this category/year under any
            # collection must not be charged again by this one.
            if FinanceFee.objects.filter(
                tenant=self.tenant, fee_category=collection.fee_category,
                academic_year=collection.academic_year, student=student,
            ).exists():
                continue
            try:
                amount, applicable = self._price_for_student(collection.fee_category, student)
            except ValidationException:
                continue
            extras = self._collection_particular_lines(collection, student)
            if not applicable and not extras:
                continue
            total = amount + sum((e.amount for e in extras), Decimal('0.00'))
            finance_fee = FinanceFee.objects.create(
                tenant=self.tenant,
                fee_category=collection.fee_category,
                fee_collection=collection,
                student=student,
                batch=batch,
                academic_year=collection.academic_year,
                balance=total,
                particular_total=total,
                transaction_date=collection.due_date,
                is_paid=False,
            )
            FinanceFeeItem.objects.bulk_create([
                FinanceFeeItem(
                    tenant=self.tenant, finance_fee=finance_fee,
                    fee_particular=p, particular_name=p.name, amount=p.amount,
                )
                for p in applicable
            ] + [
                FinanceFeeItem(
                    tenant=self.tenant, finance_fee=finance_fee,
                    fee_particular=None, particular_name=e.name, amount=e.amount,
                )
                for e in extras
            ])
            # Only invoice immediately if this collection's invoices are
            # already published - a student joining a still-draft collection
            # waits for the next bulk publish, like everyone else in it.
            if collection.status == 'published':
                invoice = InvoiceService(self.tenant).upsert_guardian_invoice(finance_fee)
                if invoice is not None:
                    enqueue_qb_sync(self.tenant, 'charge', finance_fee.id)
            created += 1
        return created

    @logged_operation('add_collection_particular')
    @transaction.atomic
    def add_collection_particular(
        self,
        collection_id: str,
        *,
        master_particular_id: str,
        amount,
        due_date=None,
        fine_slab_name: Optional[str] = None,
        description: str = "",
        applicability_rule_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Attach a master particular (e.g. PTA) to one collection and charge it
        to every student already billed in that collection.

        Idempotent: re-adding the same master particular updates its amount and
        tops up any student who doesn't yet have the line.
        """
        collection = FeeCollection.objects.filter(
            tenant=self.tenant, id=collection_id
        ).select_related('term').first()
        if not collection:
            raise NotFoundException(f"Collection {collection_id} not found")
        if collection.status in ('closed', 'archived'):
            raise ValidationException(
                f"'{collection.name}' is {collection.status}. Re-open it before "
                f"changing its particulars."
            )

        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError):
            raise ValidationException("Amount is not a valid number")
        if amount <= 0:
            raise ValidationException("Amount must be greater than zero")

        master = FeeMasterParticular.objects.filter(
            tenant=self.tenant, id=master_particular_id
        ).first()
        if not master:
            raise NotFoundException("Master particular not found")

        fine_slab = None
        if fine_slab_name:
            fine_slab = FineSlab.objects.filter(
                tenant=self.tenant, fine_name=fine_slab_name, is_active=True
            ).order_by('days_after_due').first()

        rule = None
        if applicability_rule_id:
            from core.models import FeeApplicabilityRule
            rule = FeeApplicabilityRule.objects.filter(
                tenant=self.tenant, id=applicability_rule_id
            ).first()

        fcp, was_created = FeeCollectionParticular.objects.get_or_create(
            tenant=self.tenant,
            fee_collection=collection,
            master_particular=master,
            defaults={
                'name': master.name,
                'amount': amount,
                'due_date': due_date or collection.due_date,
                'description': description or (master.description or ''),
                'fine_slab': fine_slab,
                'applicability_rule': rule,
                'is_active': True,
            },
        )
        if not was_created:
            fcp.name = master.name
            fcp.amount = amount
            fcp.due_date = due_date or collection.due_date
            fcp.description = description or (master.description or '')
            fcp.fine_slab = fine_slab
            fcp.applicability_rule = rule
            fcp.is_active = True
            fcp.save()

        charged, skipped = self._apply_particular_to_fees(collection, fcp)
        return {
            'particular_id': str(fcp.id),
            'updated': not was_created,
            'students_charged': charged,
            'students_skipped': skipped,
        }

    @logged_operation('bulk_add_collection_particular')
    def bulk_add_collection_particular(
        self,
        collection_ids: List[str],
        *,
        master_particular_id: str,
        amount,
        due_date=None,
        fine_slab_name: Optional[str] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """Apply one master particular to several collections at once.

        Each collection is handled by its own atomic add_collection_particular
        call, so a closed/archived collection (or any other failure) is reported
        as skipped rather than rolling back the whole batch.
        """
        results = []
        applied = students_charged = skipped = 0
        for cid in collection_ids:
            try:
                r = self.add_collection_particular(
                    str(cid),
                    master_particular_id=master_particular_id,
                    amount=amount,
                    due_date=due_date,
                    fine_slab_name=fine_slab_name,
                    description=description,
                )
                applied += 1
                students_charged += r['students_charged']
                results.append({'collection_id': str(cid), 'success': True, **r})
            except (ValidationException, NotFoundException) as e:
                skipped += 1
                results.append({'collection_id': str(cid), 'success': False, 'error': str(e)})
        return {
            'collections_applied': applied,
            'collections_skipped': skipped,
            'students_charged': students_charged,
            'results': results,
        }

    @logged_operation('remove_collection_particular')
    @transaction.atomic
    def remove_collection_particular(
        self, collection_id: str, particular_id: str
    ) -> Dict[str, Any]:
        """Reverse add_collection_particular: strip the line from every student's
        charge, refund the balance, then delete the FeeCollectionParticular."""
        collection = FeeCollection.objects.filter(
            tenant=self.tenant, id=collection_id
        ).first()
        if not collection:
            raise NotFoundException(f"Collection {collection_id} not found")
        fcp = FeeCollectionParticular.objects.filter(
            tenant=self.tenant, id=particular_id, fee_collection=collection
        ).first()
        if not fcp:
            raise NotFoundException("Collection particular not found")

        removed = self._strip_particular_from_fees(collection, fcp)
        fcp.delete()
        return {'students_updated': removed}

    def _apply_particular_to_fees(self, collection, fcp) -> tuple:
        """Add `fcp` as a FinanceFeeItem to every FinanceFee in `collection`
        that doesn't already have it, bumping totals/balance. Returns
        (charged, skipped)."""
        charged = skipped = 0
        fees = FinanceFee.objects.filter(
            tenant=self.tenant, fee_collection=collection
        ).select_related('student')
        for fee in fees:
            if fcp.applicability_rule and not fcp.applicability_rule.matches(fee.student):
                skipped += 1
                continue
            if FinanceFeeItem.objects.filter(
                tenant=self.tenant, finance_fee=fee,
                fee_particular__isnull=True, particular_name=fcp.name,
            ).exists():
                skipped += 1
                continue
            FinanceFeeItem.objects.create(
                tenant=self.tenant, finance_fee=fee, fee_particular=None,
                particular_name=fcp.name, amount=fcp.amount,
            )
            fee.particular_total = (fee.particular_total or Decimal('0.00')) + fcp.amount
            fee.balance = (fee.balance or Decimal('0.00')) + fcp.amount
            fee.is_paid = fee.balance <= 0
            fee.save(update_fields=['particular_total', 'balance', 'is_paid', 'updated_at'])
            if collection.status == 'published':
                invoice = InvoiceService(self.tenant).upsert_guardian_invoice(fee)
                if invoice is not None:
                    enqueue_qb_sync(self.tenant, 'charge', fee.id)
            charged += 1
        return charged, skipped

    def _strip_particular_from_fees(self, collection, fcp) -> int:
        updated = 0
        fees = FinanceFee.objects.filter(
            tenant=self.tenant, fee_collection=collection
        )
        for fee in fees:
            items = FinanceFeeItem.objects.filter(
                tenant=self.tenant, finance_fee=fee,
                fee_particular__isnull=True, particular_name=fcp.name,
            )
            line_total = sum((i.amount for i in items), Decimal('0.00'))
            if not line_total:
                continue
            items.delete()
            fee.particular_total = max(
                (fee.particular_total or Decimal('0.00')) - line_total, Decimal('0.00')
            )
            fee.balance = max(
                (fee.balance or Decimal('0.00')) - line_total, Decimal('0.00')
            )
            fee.is_paid = fee.balance <= 0
            fee.save(update_fields=['particular_total', 'balance', 'is_paid', 'updated_at'])
            if collection.status == 'published':
                invoice = InvoiceService(self.tenant).upsert_guardian_invoice(fee)
                if invoice is not None:
                    enqueue_qb_sync(self.tenant, 'charge', fee.id)
            updated += 1
        return updated

    @transaction.atomic
    def publish_invoices(self, collection_ids: List[str]) -> Dict[str, Any]:
        """Bulk-publish one or more collections: upsert every covered
        student's charge onto their guardian's consolidated FamilyInvoice
        (making it visible on the parent portal) and flip each collection
        from 'draft' to 'published'.

        Idempotent - safe to re-run on an already-published collection (e.g.
        to pick up students added since the last publish via
        sync_student_enrollment): upsert_guardian_invoice and enqueue_qb_sync
        are both no-ops for a charge that's already invoiced/synced.
        """
        collections = FeeCollection.objects.filter(tenant=self.tenant, id__in=collection_ids)
        invoice_service = InvoiceService(self.tenant)
        charges_invoiced = 0
        collections_published = 0
        for collection in collections:
            for fee in FinanceFee.objects.filter(tenant=self.tenant, fee_collection=collection):
                invoice = invoice_service.upsert_guardian_invoice(fee)
                if invoice is not None:
                    enqueue_qb_sync(self.tenant, 'charge', fee.id)
                    charges_invoiced += 1
            if collection.status == 'draft':
                collection.status = 'published'
                collection.save(update_fields=['status'])
                collections_published += 1
        return {
            'collections_processed': collections.count(),
            'collections_published': collections_published,
            'charges_invoiced': charges_invoiced,
        }

    @logged_operation('delete_fee_collection')
    def delete_collection(self, collection_id: str) -> None:
        """Delete a collection and its unpaid student obligations.

        Blocked once any linked FinanceFee has received a payment (balance <
        particular_total) — deleting would silently orphan the payment/ledger
        history instead of reversing it.
        """
        collection = FeeCollection.objects.filter(
            tenant=self.tenant, id=collection_id
        ).first()
        if not collection:
            raise NotFoundException(f"Collection {collection_id} not found")

        fees = FinanceFee.objects.filter(tenant=self.tenant, fee_collection=collection)
        has_payments = any(
            (fee.particular_total or Decimal('0.00')) - (fee.balance or Decimal('0.00')) > 0
            for fee in fees
        )
        if has_payments:
            raise ValidationException(
                f"'{collection.name}' has payments recorded against it and cannot be "
                f"deleted. Close or archive it instead."
            )

        collection.delete()

    @logged_operation('update_fee_collection')
    def update_collection(self, collection_id: str, **fields) -> FeeCollection:
        """Update a single collection's editable fields: term (by name, resolved
        per collection's batch), start_date, end_date, due_date, status. Ignores
        keys not in the allow-list so callers can pass a sparse dict of only-changed
        fields. Raises NotFoundException if the id doesn't belong to this tenant, and
        ValidationException for out-of-range values."""

        collection = FeeCollection.objects.filter(
            tenant=self.tenant, id=collection_id
        ).first()
        if not collection:
            raise NotFoundException(f"Collection {collection_id} not found")

        ALLOWED = {'term_name', 'start_date', 'end_date', 'due_date', 'status'}
        VALID_STATUSES = {c[0] for c in FeeCollection.STATUS_CHOICES}
        update_fields = []

        for key, value in fields.items():
            if key not in ALLOWED or value is None:
                continue
            if key == 'term_name':
                term = self.resolve_term_for_batch(collection.batch, value)
                if not term:
                    raise ValidationException(f"No '{value}' term exists for this collection's batch")
                setattr(collection, 'term', term)
                update_fields.append('term')
            else:
                setattr(collection, key, value)
                update_fields.append(key)

        if not update_fields:
            return collection

        # Sanity: end_date >= start_date, due_date >= start_date (only when both present)
        if (collection.end_date and collection.start_date and
                collection.end_date < collection.start_date):
            raise ValidationException("End date cannot be before start date")
        if (collection.due_date and collection.start_date and
                collection.due_date < collection.start_date):
            raise ValidationException("Due date cannot be before start date")
        if collection.status not in VALID_STATUSES:
            raise ValidationException(f"Invalid status: {collection.status}")

        collection.save(update_fields=update_fields)
        return collection

    @logged_operation('bulk_update_fee_collections')
    @transaction.atomic
    def bulk_update_collections(
        self, collection_ids: List[str], **fields
    ) -> Dict[str, Any]:
        """Apply the same field changes to many collections. Per-item
        partial-failure handling mirrors delete_collection: unknown/not-found
        ids and per-item validation errors are skipped, not fatal to the whole
        batch."""

        updated, skipped = 0, []
        for cid in collection_ids:
            try:
                self.update_collection(cid, **fields)
                updated += 1
            except NotFoundException:
                skipped.append({'id': cid, 'reason': 'not_found'})
            except ValidationException as e:
                skipped.append({'id': cid, 'reason': str(e)})

        return {'updated': updated, 'skipped': skipped}

    def list_collections(
        self, academic_year: Optional[AcademicYear] = None
    ) -> QuerySet[FeeCollection]:
        qs = FeeCollection.objects.filter(tenant=self.tenant)
        if academic_year:
            qs = qs.filter(academic_year=academic_year)

        # A FinanceFee obligation only reflects reality if the student is
        # still actively enrolled in the batch it was billed for, or if
        # money was actually collected against it (never hide real payments
        # just because the student later left the batch). Correlated
        # Exists()/Subquery() (rather than a joined OR filter) is required
        # here: joining through student__student_batches inside an OR fans
        # out one FinanceFee row per BatchStudent record the student has
        # ever had (e.g. after a transfer), which would double-count Sum().
        reality_fees = FinanceFee.objects.filter(
            tenant=self.tenant, fee_collection=OuterRef('pk')
        ).annotate(
            _is_enrolled=Exists(
                BatchStudent.objects.filter(
                    tenant=self.tenant, student_id=OuterRef('student_id'),
                    batch_id=OuterRef('batch_id'), is_active=True,
                )
            )
        ).filter(Q(_is_enrolled=True) | Q(balance__lt=F('particular_total')))

        student_count_sq = reality_fees.order_by().values('fee_collection') \
            .annotate(c=Count('id')).values('c')
        total_amount_sq = reality_fees.order_by().values('fee_collection') \
            .annotate(s=Sum('particular_total')).values('s')
        outstanding_sq = reality_fees.order_by().values('fee_collection') \
            .annotate(s=Sum('balance')).values('s')

        return qs.select_related('fee_category', 'batch', 'academic_year', 'term').annotate(
            student_count=Coalesce(
                Subquery(student_count_sq, output_field=IntegerField()), 0
            ),
            total_amount=Subquery(
                total_amount_sq, output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
            outstanding_amount=Subquery(
                outstanding_sq, output_field=DecimalField(max_digits=15, decimal_places=2)
            ),
        ).order_by('-due_date', 'name')

    def list_collections_grouped(
        self, academic_year: Optional[AcademicYear] = None
    ) -> List[Dict[str, Any]]:
        """Group list_collections() output into per-term folders, ordered by
        term.order. Collections with no term land in a trailing 'Unassigned'
        bucket rather than being dropped."""
        qs = self.list_collections(academic_year=academic_year)

        groups: Dict[Any, list] = {}
        order = []
        unassigned = []
        for c in qs:
            if c.term_id:
                if c.term_id not in groups:
                    groups[c.term_id] = {'term': c.term, 'collections': []}
                    order.append(c.term_id)
                groups[c.term_id]['collections'].append(c)
            else:
                unassigned.append(c)

        result = sorted(
            (groups[tid] for tid in order),
            key=lambda g: (g['term'].order, g['term'].name)
        )
        if unassigned:
            result.append({'term': None, 'collections': unassigned})
        return result

    def get_collection_summary(self, collection_id: str) -> Dict[str, Any]:
        collection = FeeCollection.objects.filter(
            tenant=self.tenant, id=collection_id
        ).select_related('fee_category', 'batch', 'academic_year', 'term').first()
        if not collection:
            raise NotFoundException(f"Collection {collection_id} not found")

        fees = FinanceFee.objects.filter(
            tenant=self.tenant, fee_collection=collection
        ).annotate(
            _is_enrolled=Exists(
                BatchStudent.objects.filter(
                    tenant=self.tenant, student_id=OuterRef('student_id'),
                    batch_id=OuterRef('batch_id'), is_active=True,
                )
            )
        ).filter(
            Q(_is_enrolled=True) | Q(balance__lt=F('particular_total'))
        ).select_related('student').order_by(
            'student__first_name', 'student__last_name'
        )

        rows = []
        total = Decimal('0.00')
        collected = Decimal('0.00')
        outstanding = Decimal('0.00')
        for fee in fees:
            fee_total = fee.particular_total or Decimal('0.00')
            balance = fee.balance or Decimal('0.00')
            paid = max(fee_total - balance, Decimal('0.00'))
            if balance <= 0:
                status = 'paid'
            elif paid > 0:
                status = 'partial'
            else:
                status = 'unpaid'
            rows.append({
                'student': fee.student,
                'total': fee_total,
                'paid': paid,
                'balance': balance,
                'status': status,
            })
            total += fee_total
            collected += paid
            outstanding += balance

        return {
            'collection': collection,
            'rows': rows,
            'totals': {
                'students': len(rows),
                'total': total,
                'collected': collected,
                'outstanding': outstanding,
            },
        }

    def publish_collection(self, collection_id):
        """
        Publish a fee collection: generate per-student invoices with itemized snapshots.

        This is the core invoice generation engine matching the bursar workflow:
        1. Resolve target student set from batch(es) tied to the collection's fee_category
        2. For each student, resolve applicable particulars (targeting rules + effective dates)
        3. Bulk-create FinanceFeeItem snapshots (frozen at publication time)
        4. Apply discounts (both rule-based and legacy M2M)
        5. Sync to guardian-level FamilyInvoice via InvoiceService
        """
        from core.models import (
            FeeCollection, FinanceFee, FinanceFeeItem, FeeParticular, FeeDiscount,
            BatchStudent
        )
        from core.services.invoice_service import InvoiceService
        from django.db import transaction
        import logging

        logger = logging.getLogger(__name__)

        collection = FeeCollection.objects.get(id=collection_id, tenant=self.tenant)

        if collection.status != 'draft':
            raise ValueError(f"Collection {collection.name} is not in draft status. Current status: {collection.status}")

        with transaction.atomic():
            # Step 1: Resolve target student set
            # Get all active students in the batch(es) linked to the fee_category
            target_students = set()
            batch_students = BatchStudent.objects.filter(
                batch=collection.batch,
                tenant=self.tenant,
                is_active=True
            ).select_related('student')
            for batch_student in batch_students:
                target_students.add(batch_student.student)

            logger.info(f"Publishing collection {collection.name}: targeting {len(target_students)} students")

            # Step 2: Resolve active particulars and discounts for this category
            active_particulars = FeeParticular.objects.filter(
                fee_category=collection.fee_category,
                tenant=self.tenant,
                is_active=True
            )
            active_discounts = FeeDiscount.objects.filter(
                fee_category=collection.fee_category,
                tenant=self.tenant,
                is_active=True
            )

            # Step 3: For each student, generate invoice
            for student in target_students:
                # Get or create FinanceFee (idempotent — skip if already published)
                finance_fee, created = FinanceFee.objects.get_or_create(
                    tenant=self.tenant,
                    student=student,
                    fee_category=collection.fee_category,
                    academic_year=collection.academic_year,
                    defaults={
                        'balance': 0,
                        'batch': collection.batch,
                        'fee_collection': collection,
                        'particular_total': 0,
                        'discount_amount': 0,
                    }
                )

                # If already published (has items), skip regeneration
                if finance_fee.items.exists():
                    logger.info(f"Skipping {student.admission_no}: already has itemized invoice")
                    continue

                # Filter particulars that apply to this student (targeting rules + effective dates)
                from datetime import date
                today = date.today()
                applicable_particulars = []
                for particular in active_particulars:
                    # Check effective/expiry dates
                    if particular.effective_date and today < particular.effective_date:
                        continue  # Not yet effective
                    if particular.expiry_date and today > particular.expiry_date:
                        continue  # Expired

                    # Check targeting rule
                    if particular.applicability_rule is None:
                        # No rule = applies to all
                        applicable_particulars.append(particular)
                    elif particular.applicability_rule.matches(student):
                        applicable_particulars.append(particular)

                # Bulk-create FinanceFeeItem snapshots (immutable)
                items_to_create = [
                    FinanceFeeItem(
                        tenant=self.tenant,
                        finance_fee=finance_fee,
                        fee_particular=p,
                        particular_name=p.name,  # Snapshot at publication time
                        amount=p.amount,  # Snapshot at publication time
                    )
                    for p in applicable_particulars
                ]
                FinanceFeeItem.objects.bulk_create(items_to_create)

                # Compute total from items
                total_amount = sum(Decimal(str(p.amount)) for p in applicable_particulars)

                # Filter discounts that apply to this student (both rule and legacy M2M + effective dates)
                applicable_discounts = []
                for discount in active_discounts:
                    # Check effective/expiry dates
                    if discount.effective_date and today < discount.effective_date:
                        continue  # Not yet effective
                    if discount.expiry_date and today > discount.expiry_date:
                        continue  # Expired

                    # Check rule-based targeting (new path)
                    if discount.applicability_rule is not None:
                        if discount.applicability_rule.matches(student):
                            applicable_discounts.append(discount)
                            continue
                    # Check legacy M2M targeting (existing path)
                    if discount.batches.filter(id=collection.batch.id).exists():
                        applicable_discounts.append(discount)
                        continue
                    if discount.students.filter(id=student.id).exists():
                        applicable_discounts.append(discount)

                # Compute discount amount
                discount_amount = Decimal('0.00')
                for discount in applicable_discounts:
                    discount_amount += Decimal(str(discount.calculate_discount(total_amount)))

                # Update FinanceFee with computed totals
                finance_fee.particular_total = total_amount
                finance_fee.discount_amount = discount_amount
                finance_fee.balance = total_amount - discount_amount
                # Generate invoice number
                finance_fee.invoice_number = f"INV-{collection.academic_year.name}-{str(finance_fee.id)[:8]}"
                finance_fee.fee_collection = collection
                finance_fee.save()

                # Sync to guardian-level FamilyInvoice
                invoice_service = InvoiceService(tenant=self.tenant)
                invoice_service.upsert_guardian_invoice(finance_fee)

            # Step 4: Mark collection as published
            collection.status = 'published'
            collection.is_active = True  # Keep in sync
            collection.save()

            logger.info(f"Published collection {collection.name} - {len(target_students)} invoices generated")

    def close_collection(self, collection_id):
        """Close a published collection (no new mutations allowed after this)"""
        from core.models import FeeCollection

        collection = FeeCollection.objects.get(id=collection_id, tenant=self.tenant)

        if collection.status not in ['published', 'draft']:
            raise ValueError(
                f"Can only close published or draft collections. Current status: {collection.status}"
            )

        collection.status = 'closed'
        collection.is_active = False
        collection.save()

    def archive_collection(self, collection_id):
        """Archive a closed collection (permanent status)"""
        from core.models import FeeCollection

        collection = FeeCollection.objects.get(id=collection_id, tenant=self.tenant)

        if collection.status != 'closed':
            raise ValueError(f"Can only archive closed collections. Current status: {collection.status}")

        collection.status = 'archived'
        collection.save()

    def generate_next_recurrence(self, collection_id: str) -> Dict[str, Any]:
        """
        Generate the next recurrence of a recurring collection.
        Creates a new draft collection with parent_collection set.
        Called by Celery beat or manually by admin.
        """
        from core.models import FeeCollection
        from datetime import date
        from dateutil.relativedelta import relativedelta

        parent_collection = FeeCollection.objects.get(id=collection_id, tenant=self.tenant)

        if parent_collection.frequency == 'one_time':
            raise ValidationException(f"Collection {parent_collection.name} is not recurring (frequency=one_time)")

        # Calculate dates for next recurrence
        today = date.today()
        current_start = parent_collection.start_date
        current_end = parent_collection.end_date
        current_due = parent_collection.due_date

        # Advance dates based on frequency
        if parent_collection.frequency == 'monthly':
            next_start = current_start + relativedelta(months=1)
            next_end = current_end + relativedelta(months=1)
            next_due = current_due + relativedelta(months=1)
            next_next_gen = today + relativedelta(months=2)
        elif parent_collection.frequency == 'termly':
            next_start = current_start + relativedelta(months=3)
            next_end = current_end + relativedelta(months=3)
            next_due = current_due + relativedelta(months=3)
            next_next_gen = today + relativedelta(months=6)
        elif parent_collection.frequency == 'yearly':
            next_start = current_start + relativedelta(years=1)
            next_end = current_end + relativedelta(years=1)
            next_due = current_due + relativedelta(years=1)
            next_next_gen = today + relativedelta(years=2)
        else:
            raise ValidationException(f"Unknown frequency: {parent_collection.frequency}")

        # Create next recurrence in draft status
        recurrence_name = f"{parent_collection.name} - {next_start.strftime('%b %Y')}"
        next_collection = FeeCollection.objects.create(
            tenant=self.tenant,
            name=recurrence_name,
            fee_category=parent_collection.fee_category,
            batch=parent_collection.batch,
            start_date=next_start,
            end_date=next_end,
            due_date=next_due,
            academic_year=parent_collection.academic_year,
            status='draft',
            is_active=True,
            frequency=parent_collection.frequency,
            late_fee_rule=parent_collection.late_fee_rule,
            parent_collection=parent_collection,
            next_generation_date=next_next_gen,
        )

        # Update parent's next_generation_date
        parent_collection.next_generation_date = next_next_gen
        parent_collection.save()

        return {
            'parent_collection_id': collection_id,
            'next_recurrence': next_collection,
            'next_recurrence_id': next_collection.id,
        }
