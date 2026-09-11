import itertools
import json
import logging
from typing import Dict, Any, List
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404, HttpResponse
from django.views.generic import TemplateView, View, ListView, RedirectView
from django.db import transaction
from django.contrib import messages
from django.urls import reverse
from django.db.models import Q, Sum, Count, Min, Max
from django.core.paginator import Paginator
from datetime import date, timedelta

from core.models import (
    FeeCategory,
    FinanceFee,
    BatchFeeCategory,
    BatchFeeCategoryStudent,
    Student,
    Batch,
    BatchStudent,
    AcademicYear,
    FinanceTransaction,
    FeeTransaction,
    FinanceTransactionCategory,
    QuickBooksFeePaymentSync,
    QuickBooksFeeInvoiceSync,
    QuickBooksCustomerSync,
    FeeParticular,
    FeeMasterParticular,
    FeeDiscount,
    StudentCategory,
    FeeApplicabilityRule,
    FineSlab,
    Employee,
    FeeCollection,
)
from core.services.finance_service import FinanceService
from core.services.quickbooks_service import QuickBooksService
from core.services.quickbooks_fee_sync_service import QuickBooksFeeSync
from core.services.currency_service import CurrencyService
from core.services.fee_reporting_service import FeeReportingService
from core.services.exceptions import ValidationException, ServiceException, NotFoundException, BusinessLogicException, DuplicateException
from core.view_modules.finance_year_context import (
    build_year_context, resolve_selected_year, resolve_student_fee_collections,
)

logger = logging.getLogger(__name__)


class FeeCategoryListView(ListView):
    """List and manage fee categories"""
    model = FeeCategory
    template_name = 'core/fees/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20
    
    def get_queryset(self):
        school = getattr(self.request, 'tenant', None)
        if not school:
            return FeeCategory.objects.none()
        
        queryset = FeeCategory.objects.filter(
            tenant=school,
            is_deleted=False
        ).annotate(
            # Per-category assignment count in one GROUP BY query instead of a
            # COUNT round-trip per row in get_context_data.
            batch_assignments=Count('batchfeecategory')
        ).order_by('name')

        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school'] = getattr(self.request, 'tenant', None)
        context['header_actions'] = [
            {'label': 'Add Category', 'variant': 'primary', 'icon': 'fa-plus', 'attrs': 'data-bs-toggle="modal" data-bs-target="#createCategoryModal"'},
        ]
        context['table_columns'] = ['Category Name', 'Description', 'Batch Assignments', 'Created Date', 'Actions']
        context['empty_message'] = (
            'No categories match your search criteria.' if self.request.GET.get('search')
            else 'Create your first fee category to get started.'
        )
        context['create_category_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Create Category', 'variant': 'primary', 'type': 'submit'},
        ]
        context['edit_category_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Update Category', 'variant': 'primary', 'type': 'submit'},
        ]
        context['delete_category_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Delete Category', 'variant': 'danger', 'attrs': 'id="confirmDeleteCategory"'},
        ]
        context['category_list_clear_url'] = reverse('core:fee_categories') if self.request.GET.get('search') else ''
        return context


class FeeCategoryCreateView(View):
    """Create, update, or delete a fee category"""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        action = request.POST.get('action', 'create')

        try:
            if action == 'update':
                return self._update(request, school)
            elif action == 'delete':
                return self._delete(request, school)
            else:
                return self._create(request, school)
        except Exception as e:
            logger.error(f"Error in fee category POST: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    def _create(self, request, school):
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            return JsonResponse({'error': 'Category name is required'}, status=400)

        # New fee categories default to the school's active academic year.
        active_year = AcademicYear.objects.filter(
            tenant=school, is_active=True
        ).first()

        if FeeCategory.objects.filter(
            tenant=school,
            name__iexact=name,
            academic_year=active_year,
            is_deleted=False
        ).exists():
            return JsonResponse({'error': 'Fee category already exists for the active academic year'}, status=400)

        category = FeeCategory.objects.create(
            tenant=school,
            name=name,
            description=description,
            academic_year=active_year,
        )

        return JsonResponse({
            'success': True,
            'message': f'Fee category "{name}" created successfully',
            'category_id': str(category.id)
        })

    def _update(self, request, school):
        category_id = request.POST.get('category_id')
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not category_id:
            return JsonResponse({'error': 'Category ID is required'}, status=400)
        if not name:
            return JsonResponse({'error': 'Category name is required'}, status=400)

        try:
            category = FeeCategory.objects.get(id=category_id, tenant=school, is_deleted=False)
        except FeeCategory.DoesNotExist:
            return JsonResponse({'error': 'Fee category not found'}, status=404)

        if FeeCategory.objects.filter(
            tenant=school,
            name__iexact=name,
            is_deleted=False
        ).exclude(id=category.id).exists():
            return JsonResponse({'error': 'Fee category already exists'}, status=400)

        category.name = name
        category.description = description
        category.save(update_fields=['name', 'description'])

        return JsonResponse({
            'success': True,
            'message': f'Fee category "{name}" updated successfully',
            'category_id': str(category.id)
        })

    def _delete(self, request, school):
        category_id = request.POST.get('category_id')

        if not category_id:
            return JsonResponse({'error': 'Category ID is required'}, status=400)

        try:
            category = FeeCategory.objects.get(id=category_id, tenant=school, is_deleted=False)
        except FeeCategory.DoesNotExist:
            return JsonResponse({'error': 'Fee category not found'}, status=404)

        if BatchFeeCategory.objects.filter(tenant=school, fee_category=category).exists():
            return JsonResponse({
                'error': 'Cannot delete: this category is still assigned to one or more batches'
            }, status=400)

        if FinanceFee.objects.filter(tenant=school, fee_category=category).exists():
            return JsonResponse({
                'error': 'Cannot delete: students already have charges recorded under this category'
            }, status=400)

        category.is_deleted = True
        category.save(update_fields=['is_deleted'])

        return JsonResponse({
            'success': True,
            'message': f'Fee category "{category.name}" deleted successfully'
        })


class BatchFeeAssignmentView(TemplateView):
    """Assign fees to batches"""
    template_name = 'core/fees/batch_assignment.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        from collections import defaultdict
        from core.models import Term

        # Get fee categories
        fee_categories = FeeCategory.objects.filter(
            tenant=school,
            is_deleted=False
        ).order_by('name')

        # Get batches
        batches = Batch.objects.filter(
            tenant=school,
            is_deleted=False,
            is_active=True
        ).select_related('course', 'academic_year').order_by('name')

        # Get existing assignments
        assignments = BatchFeeCategory.objects.filter(
            tenant=school
        ).select_related('fee_category', 'batch', 'batch__course')

        # --- Group assignments and categories by academic term -------------
        # A fee category has no term column of its own; its term(s) are those
        # of the fee collections (billing runs) it is used in. Collections are
        # termly, so this is the natural axis to organise the screen around.
        terms = {
            t.id: t for t in Term.objects.filter(tenant=school)
            .select_related('academic_year').order_by('academic_year', 'order')
        }

        pair_terms = defaultdict(set)   # (fee_category_id, batch_id) -> {term_id}
        cat_terms = defaultdict(set)    # fee_category_id            -> {term_id}
        for cat_id, batch_id, term_id in FeeCollection.objects.filter(
            tenant=school, term__isnull=False
        ).values_list('fee_category_id', 'batch_id', 'term_id'):
            pair_terms[(cat_id, batch_id)].add(term_id)
            cat_terms[cat_id].add(term_id)

        def _term_sort_key(term_id):
            term = terms.get(term_id)
            if term is None:
                return (1, 0, '')
            return (0, term.order, str(term.academic_year_id))

        def _build_groups(item_terms_getter, items):
            buckets = defaultdict(list)
            for item in items:
                tids = item_terms_getter(item) or {None}
                for tid in tids:
                    buckets[tid].append(item)
            return [
                {'term': terms.get(tid), 'items': rows}
                for tid, rows in sorted(
                    buckets.items(), key=lambda kv: _term_sort_key(kv[0])
                )
            ]

        grouped_assignments = _build_groups(
            lambda a: pair_terms.get((a.fee_category_id, a.batch_id)),
            list(assignments),
        )
        grouped_categories = _build_groups(
            lambda c: cat_terms.get(c.id),
            list(fee_categories),
        )

        context.update({
            'school': school,
            'fee_categories': fee_categories,
            'grouped_categories': grouped_categories,
            'grouped_assignments': grouped_assignments,
            'batches': batches,
            'assignments': assignments,
            'back_url': self.request.GET.get('back', reverse('core:fee_structure')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Fee Structure', 'url': reverse('core:fee_structure')},
                {'label': 'Batch Assignment'},
            ],
        })

        return context


class BatchFeeAssignmentCreateView(View):
    """Create batch fee assignment(s) - supports multiple batches, with optional student scoping"""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            fee_category_id = request.POST.get('fee_category_id')
            batch_ids = request.POST.getlist('batch_ids')
            student_ids = request.POST.getlist('student_ids')  # optional

            if not fee_category_id or not batch_ids:
                return JsonResponse({'error': 'Fee category and batch(es) are required'}, status=400)

            svc = FinanceService(school)
            result = svc.assign_fee_to_batches(
                fee_category_id, batch_ids,
                student_ids=student_ids if student_ids else None
            )

            if result['created_count'] == 0:
                return JsonResponse({
                    'error': 'No new assignments created (all selected batches already have this fee)'
                }, status=400)

            message = f'Assigned fee to {result["created_count"]} batch{"es" if result["created_count"] != 1 else ""}'
            if result['skipped_batches']:
                message += f'. {len(result["skipped_batches"])} already had this assignment'
            if result['zero_student_batches']:
                message += f'. Warning: none of the selected students are enrolled in: {", ".join(result["zero_student_batches"])}'

            return JsonResponse({
                'success': True,
                'message': message,
                'created_count': result['created_count'],
                'skipped_count': len(result['skipped_batches']),
                'assignment_ids': result['assignment_ids'],
                'zero_student_batches': result['zero_student_batches'],
            })

        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error creating batch fee assignment: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class BatchFeeAssignmentDeleteView(View):
    """Delete a batch fee assignment"""

    def delete(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        assignment_id = kwargs.get('pk')
        if not assignment_id:
            return JsonResponse({'error': 'Assignment ID is required'}, status=400)

        try:
            assignment = get_object_or_404(
                BatchFeeCategory,
                id=assignment_id,
                tenant=school
            )

            fee_category_name = assignment.fee_category.name
            batch_name = assignment.batch.name
            assignment.delete()

            return JsonResponse({
                'success': True,
                'message': f'Assignment "{fee_category_name}" from "{batch_name}" deleted successfully'
            })

        except Http404:
            return JsonResponse({'error': 'Assignment not found'}, status=404)
        except Exception as e:
            logger.error(f"Error deleting batch fee assignment: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class BatchFeeAssignmentBulkDeleteView(View):
    """JSON/fetch bulk-delete for batch fee assignments"""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            payload = json.loads(request.body)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

        ids = payload.get('assignment_ids') or []
        if not ids:
            return JsonResponse({'error': 'Select at least one assignment to delete.'}, status=400)

        svc = FinanceService(school)
        result = svc.bulk_delete_batch_fee_assignments(ids)

        return JsonResponse({
            'success': True,
            'deleted_count': result['deleted_count'],
            'message': f"Deleted {result['deleted_count']} assignment(s)",
        })


class BatchFeeAssignmentStudentsView(View):
    """JSON endpoint: active students currently enrolled in a given batch"""

    def get(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        batch_id = request.GET.get('batch_id')

        if not batch_id:
            return JsonResponse({'error': 'Missing batch_id'}, status=400)

        rows = BatchStudent.objects.filter(
            tenant=school, batch_id=batch_id, is_active=True
        ).select_related('student').order_by('student__first_name')

        students = [
            {
                'id': str(r.student.id),
                'name': f"{r.student.first_name} {r.student.last_name}",
                'admission_no': r.student.admission_no or ''
            }
            for r in rows
        ]

        return JsonResponse({'students': students})


class StudentFeeManagementView(TemplateView):
    """Manage individual student fees"""
    template_name = 'core/fees/student_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        # Resolve the selected academic year; balances/history are scoped to it.
        selected_year = resolve_selected_year(self.request, school)

        student_id = self.request.GET.get('student_id') or self.request.GET.get('student')
        batch_id = self.request.GET.get('batch_id')
        student = None

        if student_id:
            try:
                student = Student.objects.get(
                    id=student_id,
                    tenant=school,
                    is_active=True
                )

                # Get student's outstanding fees (scoped to the selected year)
                outstanding_fees = FinanceFee.objects.filter(
                    tenant=school,
                    student=student,
                    balance__gt=0
                ).select_related('fee_category').order_by(
                    'fee_category__name', 'transaction_date'
                )
                if selected_year is not None:
                    outstanding_fees = outstanding_fees.filter(academic_year=selected_year)

                # Get student's fee ledger (scoped to the selected year) — the
                # per-student FeeTransaction ledger (payments, discounts, fines,
                # refunds, charges), which carries ids needed for reversal.
                fee_transactions_qs = FeeTransaction.objects.filter(
                    tenant=school,
                    student=student,
                ).select_related('fee_category', 'collected_by', 'fee_particular').order_by('-transaction_date')
                if selected_year is not None:
                    fee_transactions_qs = fee_transactions_qs.filter(academic_year=selected_year)

                # Hide reversed payments and their compensating refund rows from
                # the ledger/history shown here: a reversal posts a
                # FeeTransaction(transaction_type='refund',
                # reference_number='REVERSAL:<payment id>'). The rows stay in the
                # DB for audit, but a reversed payment is a non-event to the
                # cashier, so neither it nor the refund appears in the history.
                all_txns = list(fee_transactions_qs)
                reversed_payment_ids = {
                    (t.reference_number or '').split(':', 1)[1]
                    for t in all_txns
                    if t.transaction_type == 'refund'
                    and (t.reference_number or '').startswith('REVERSAL:')
                }

                def _is_reversal_noise(t):
                    if t.transaction_type == 'refund' and (t.reference_number or '').startswith('REVERSAL:'):
                        return True
                    if t.transaction_type == 'payment' and str(t.id) in reversed_payment_ids:
                        return True
                    return False

                fee_transactions = [t for t in all_txns if not _is_reversal_noise(t)]

                # Current enrolment (for display); prefer the selected year's batch.
                current_batch_qs = BatchStudent.objects.filter(
                    student=student, tenant=school, is_active=True
                ).select_related('batch')
                if selected_year is not None:
                    current_batch_qs = current_batch_qs.filter(batch__academic_year=selected_year)
                current_batch = current_batch_qs.first()

                # Attach a per-charge status (overdue if unpaid > 30 days).
                overdue_cutoff = date.today() - timedelta(days=30)
                outstanding_list = list(outstanding_fees)
                any_overdue = False

                # One-time charges added via "Add Particular" are removable
                # while still untouched by any payment/discount/fine - see
                # RemoveStudentChargeView / FinanceService.remove_student_charge.
                # Matched back to their FinanceFee via the ledger row's
                # "CHARGE:<finance_fee_id>" reference_number tag.
                removable_charges = {
                    t.reference_number.split(':', 1)[1]: t
                    for t in FeeTransaction.objects.filter(
                        tenant=school, student=student, transaction_type='charge',
                        reference_number__startswith='CHARGE:',
                    )
                }

                for fee in outstanding_list:
                    if fee.transaction_date and fee.transaction_date < overdue_cutoff:
                        fee.display_status = 'overdue'
                        any_overdue = True
                    else:
                        fee.display_status = 'outstanding'

                    charge_txn = removable_charges.get(str(fee.id))
                    fee.remove_charge_txn_id = (
                        charge_txn.id
                        if charge_txn and fee.fee_collection_id is None and fee.balance == charge_txn.amount
                        else None
                    )

                total_outstanding = sum((f.balance for f in outstanding_list), Decimal('0.00'))
                # Overall student status for the selected year.
                has_payments = any(t.transaction_type == 'payment' for t in fee_transactions)
                if total_outstanding <= 0:
                    overall_status = 'paid'
                elif any_overdue:
                    overall_status = 'overdue'
                elif has_payments:
                    overall_status = 'partial'
                else:
                    overall_status = 'outstanding'

                # Per-particular breakdown for the itemized collect-fee table.
                # Categories with no defined particulars simply don't appear
                # here; the lump-sum fallback below still covers them.
                particular_breakdown = FinanceService(school).get_student_particular_breakdown(
                    str(student.id), selected_year
                )

                # Navigation: get list of students to enable < > arrows
                students_qs = Student.objects.filter(
                    tenant=school,
                    is_active=True
                ).order_by('first_name', 'last_name')

                # If batch_id is provided, filter to students in that batch
                if batch_id:
                    students_qs = students_qs.filter(
                        batchstudent__batch_id=batch_id,
                        batchstudent__tenant=school,
                        batchstudent__is_active=True
                    ).distinct()

                students_list = list(students_qs.values_list('id', flat=True))

                # Find current student position
                try:
                    current_index = students_list.index(student.id)
                    has_prev = current_index > 0
                    has_next = current_index < len(students_list) - 1
                    prev_student_id = students_list[current_index - 1] if has_prev else None
                    next_student_id = students_list[current_index + 1] if has_next else None

                    # Build navigation URLs
                    query_params = f"?student_id={{}}"
                    if batch_id:
                        query_params += f"&batch_id={batch_id}"
                    if selected_year:
                        query_params += f"&academic_year={selected_year.id}"

                    prev_url = f"{query_params.format(prev_student_id)}" if has_prev else None
                    next_url = f"{query_params.format(next_student_id)}" if has_next else None

                    context.update({
                        'student_position': f"{current_index + 1} of {len(students_list)}",
                        'has_prev': has_prev,
                        'has_next': has_next,
                        'prev_url': prev_url,
                        'next_url': next_url,
                    })
                except (ValueError, IndexError):
                    pass

                # Fee Collection selector (Fedena-style): which billing cycle
                # is this payment being recorded against.
                fee_collections, selected_fee_collection_id = resolve_student_fee_collections(
                    self.request, school, student, selected_year,
                )
                collection_summary = None
                if selected_fee_collection_id:
                    fee_collection = fee_collections.filter(id=selected_fee_collection_id).first()
                    if fee_collection:
                        try:
                            collection_summary = FeeReportingService(school).student_collection_receipt(
                                student, fee_collection
                            )
                        except NotFoundException:
                            collection_summary = None

                # Guardian's/Father's name: prefer the student's designated
                # immediate contact, else the first linked guardian.
                guardian_name = FeeReportingService(school).resolve_guardian_name(student)

                # Financial-year mismatch warning: selected year vs. the
                # school's currently active academic year.
                active_academic_year = AcademicYear.objects.filter(
                    tenant=school, is_active=True
                ).first()
                year_mismatch = bool(
                    selected_year and active_academic_year
                    and selected_year.id != active_academic_year.id
                )

                # Group the ledger into receipts: payment rows sharing a
                # reference_number belong to one submission (itemized, or a
                # lump-sum now split across particulars) and are shown as one
                # expandable row. Non-payment rows (discount/fine/refund/
                # adjustment) and legacy payments with no reference each stay
                # their own single-line group.
                def _receipt_group_key(t):
                    if t.transaction_type == 'payment' and t.reference_number:
                        return t.reference_number
                    return f"txn-{t.id}"

                ledger_receipts = []
                for _, rows in itertools.groupby(fee_transactions, key=_receipt_group_key):
                    txns = list(rows)
                    ledger_receipts.append({
                        'transactions': txns,
                        'total_amount': sum((t.amount for t in txns), Decimal('0.00')),
                    })

                context.update({
                    'student': student,
                    'current_batch': current_batch,
                    'outstanding_fees': outstanding_list,
                    'fee_transactions': fee_transactions,
                    'ledger_receipts': ledger_receipts,
                    'total_outstanding': total_outstanding,
                    'overall_status': overall_status,
                    'particular_breakdown': particular_breakdown,
                    'fee_collections': fee_collections,
                    'selected_fee_collection_id': selected_fee_collection_id,
                    'collection_summary': collection_summary,
                    'guardian_name': guardian_name,
                    'year_mismatch': year_mismatch,
                })

            except Student.DoesNotExist:
                messages.error(self.request, 'Student not found')

        # Get fee categories for manual fee assignment
        fee_categories = FeeCategory.objects.filter(
            tenant=school,
            is_deleted=False
        ).order_by('name')

        # Get active master particulars (reusable name templates) for the Add Charge modal
        master_particulars = FeeMasterParticular.objects.filter(
            tenant=school, is_active=True
        ).order_by('name')

        # Get active batches for batch filtering
        batches = Batch.objects.filter(
            tenant=school,
            is_active=True,
            is_deleted=False
        ).select_related('course').order_by('name')

        # Get fine slabs for fine selection
        fine_slabs = FineSlab.objects.filter(
            tenant=school,
            is_active=True
        ).order_by('days_after_due')

        # Get discounts for discount selection
        discounts = FeeDiscount.objects.filter(
            tenant=school,
            is_active=True
        ).order_by('name')

        # Active employees for the Cashier selector on the payment modals
        employees = Employee.objects.filter(
            tenant=school, status=True
        ).order_by('first_name', 'last_name')

        context.update({
            'school': school,
            'fee_categories': fee_categories,
            'master_particulars': master_particulars,
            'batches': batches,
            'fine_slabs': fine_slabs,
            'discounts': discounts,
            'employees': employees,
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
            'batch_id': batch_id,
            'payment_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Record Payment', 'variant': 'primary', 'type': 'submit', 'icon': 'fa-check'},
            ],
            'reversal_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Reverse Payment', 'variant': 'danger', 'type': 'submit', 'icon': 'fa-undo'},
            ],
            'remove_charge_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Remove Charge', 'variant': 'danger', 'type': 'submit', 'icon': 'fa-trash-alt'},
            ],
            'waiver_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Grant Waiver', 'variant': 'primary', 'type': 'submit', 'icon': 'fa-check'},
            ],
            'add_particular_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Add Particular', 'variant': 'primary', 'type': 'submit', 'icon': 'fa-check'},
            ],
            'add_discount_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Apply Discount', 'variant': 'primary', 'type': 'submit', 'icon': 'fa-check'},
            ],
            'add_fine_footer': [
                {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
                {'label': 'Add Fine', 'variant': 'danger', 'type': 'submit', 'icon': 'fa-check'},
            ],
        })
        context.update(build_year_context(self.request, school))

        return context


class StudentFeePaymentView(View):
    """Process fee payment for a student"""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        allocations_raw = request.POST.get('allocations')
        if allocations_raw:
            return self._process_itemized(request, school, allocations_raw)
        return self._process_lump_sum(request, school)

    def _process_itemized(self, request, school, allocations_raw):
        """Itemized, multi-category/particular payment (Fedena-style collect-fee)."""
        student_id = request.POST.get('student_id')
        payment_method = request.POST.get('payment_method', 'cash')
        academic_year_id = request.POST.get('academic_year')
        reference_number = request.POST.get('reference_number', '').strip() or None
        collected_by_id = request.POST.get('cashier_employee_id') or None
        notes = request.POST.get('description', '').strip() or None

        if not student_id:
            return JsonResponse({'error': 'Student is required'}, status=400)

        try:
            allocations = json.loads(allocations_raw)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid allocations payload'}, status=400)

        if not allocations:
            return JsonResponse({'error': 'At least one fee allocation is required'}, status=400)

        academic_year = None
        if academic_year_id:
            academic_year = AcademicYear.objects.filter(
                id=academic_year_id, tenant=school
            ).first()

        try:
            result = FinanceService(school).process_itemized_fee_payment(
                student_id=student_id,
                allocations=allocations,
                payment_date=date.today(),
                payment_method=payment_method,
                academic_year=academic_year,
                reference_number=reference_number,
                collected_by_id=collected_by_id,
                notes=notes,
            )
            return JsonResponse({
                'success': True,
                'message': f"Payment of {result['total_amount']} processed successfully",
                'total_amount': float(result['total_amount']),
                'allocations': [
                    {**a, 'amount': float(a['amount']), 'balance': float(a['balance'])}
                    for a in result['allocations']
                ],
                'transaction_id': result.get('transaction_id'),
                'receipt_no': result.get('reference_number'),
            })
        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except (BusinessLogicException, DuplicateException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error processing itemized fee payment: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    def _process_lump_sum(self, request, school):
        try:
            student_id = request.POST.get('student_id')
            fee_category_id = request.POST.get('fee_category_id')
            payment_amount = request.POST.get('payment_amount')
            payment_method = request.POST.get('payment_method', 'cash')
            description = request.POST.get('description', '')
            academic_year_id = request.POST.get('academic_year')
            reference_number = request.POST.get('reference_number', '').strip() or None
            collected_by_id = request.POST.get('cashier_employee_id') or None

            if not all([student_id, fee_category_id, payment_amount]):
                return JsonResponse({'error': 'All fields are required'}, status=400)

            try:
                payment_amount = Decimal(payment_amount)
                if payment_amount <= 0:
                    return JsonResponse({'error': 'Payment amount must be positive'}, status=400)
            except (ValueError, TypeError, InvalidOperation):
                return JsonResponse({'error': 'Invalid payment amount format'}, status=400)

            finance_service = FinanceService(school)

            # Resolve the academic year the payment applies to (selected in the UI,
            # else the active year via the service default).
            academic_year = None
            if academic_year_id:
                academic_year = AcademicYear.objects.filter(
                    id=academic_year_id, tenant=school
                ).first()

            with transaction.atomic():
                # Process the payment
                transaction_obj, student_fee = finance_service.process_fee_payment(
                    student_id=student_id,
                    fee_category_id=fee_category_id,
                    payment_amount=payment_amount,
                    payment_date=date.today(),
                    description=description.strip() or None,
                    payment_method=payment_method,
                    academic_year=academic_year,
                    reference_number=reference_number,
                    collected_by_id=collected_by_id,
                )

            return JsonResponse({
                'success': True,
                'message': f'Payment of {payment_amount} processed successfully',
                'remaining_balance': float(student_fee.balance),
                'transaction_id': str(transaction_obj.id),
                'receipt_no': transaction_obj.reference_number,
            })

        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except (BusinessLogicException, DuplicateException) as e:
            # New backend guards: no matching charge / duplicate payment.
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error processing fee payment: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class BatchFeeReportView(TemplateView):
    """Batch-based fee report showing students by payment status and term"""
    template_name = 'core/fees/batch_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        # Get filter parameters
        batch_id = self.request.GET.get('batch_id')
        selected_status = self.request.GET.get('status', '')
        group_by = self.request.GET.get('group_by', 'batch')

        # Resolve the selected academic year; the batch list is scoped to it
        # (this replaces the old term1/2/3 filter).
        selected_year = resolve_selected_year(self.request, school)

        # Get active batches for the selected year
        batches = Batch.objects.filter(
            tenant=school,
            is_deleted=False,
            is_active=True
        ).select_related('course', 'academic_year').order_by('name')
        if selected_year is not None:
            batches = batches.filter(academic_year=selected_year)

        context['batches'] = batches
        context['selected_status'] = selected_status
        context['group_by'] = group_by
        context.update(build_year_context(self.request, school))

        # Add currency context
        currency_service = CurrencyService(school)
        context.update(currency_service.get_currency_context())
        context['currency_service'] = currency_service

        # If group_by=student, force all-batches aggregation
        if group_by == 'student':
            batch_id = 'all'

        if batch_id:
            if batch_id == 'all':
                # Aggregate data across all batches
                context['selected_batch'] = None
                context['show_all_batches'] = True

                # Collect data for all batches
                all_student_fees = []
                batch_summary = {
                    'total_students': 0,
                    'total_fees_due': Decimal('0.00'),
                    'total_collected': Decimal('0.00'),
                    'total_outstanding': Decimal('0.00'),
                    'paid_in_full_count': 0,
                    'partial_payment_count': 0,
                    'outstanding_count': 0,
                    'overdue_count': 0,
                }

                for batch in batches:
                    batch_data, batch_students = self._get_batch_fee_data(
                        school, batch, selected_status
                    )

                    # Merge batch data into all_student_fees
                    for student_fee in batch_students:
                        student_fee['batch'] = batch  # Add batch reference
                        all_student_fees.append(student_fee)

                    # Accumulate summary
                    batch_summary['total_students'] += batch_data['total_students']
                    batch_summary['total_fees_due'] += batch_data['total_fees_due']
                    batch_summary['total_collected'] += batch_data['total_collected']
                    batch_summary['total_outstanding'] += batch_data['total_outstanding']
                    batch_summary['paid_in_full_count'] += batch_data['paid_in_full_count']
                    batch_summary['partial_payment_count'] += batch_data['partial_payment_count']
                    batch_summary['outstanding_count'] += batch_data['outstanding_count']
                    batch_summary['overdue_count'] += batch_data['overdue_count']

                # Sort by student name if in student-wise mode
                if group_by == 'student':
                    all_student_fees.sort(key=lambda r: (r['student'].first_name or '', r['student'].last_name or ''))
                    context['show_all_batches'] = True

                context['batch_summary'] = batch_summary
                context['student_fees'] = all_student_fees
            else:
                try:
                    selected_batch = Batch.objects.get(
                        id=batch_id,
                        tenant=school,
                        is_deleted=False
                    )
                    context['selected_batch'] = selected_batch
                    context['show_all_batches'] = False

                    # Get batch summary and student fees
                    batch_summary, student_fees = self._get_batch_fee_data(
                        school, selected_batch, selected_status
                    )

                    context['batch_summary'] = batch_summary
                    context['student_fees'] = student_fees

                except Batch.DoesNotExist:
                    pass

        # Add navigation context
        context.update({
            'back_url': self.request.GET.get('back', reverse('core:fee_dashboard')),
            'crumbs': [
                {'label': 'Fees', 'url': reverse('core:fee_dashboard')},
                {'label': 'Batch Report'},
            ],
        })

        return context
    
    def _get_batch_fee_data(self, school, batch, status_filter):
        """Get comprehensive fee data for a batch (scoped to the batch's year)

        Optimized for bulk loading: queries are done once for all students,
        not per-student in a loop (N+1 prevention).
        """
        from core.models import BatchStudent

        # Get all students in the batch
        batch_students = BatchStudent.objects.filter(
            tenant=school,
            batch=batch,
            is_active=True
        ).select_related('student')

        # The batch is tied to a specific academic year; all figures below are
        # scoped to it so a student's prior-year balances never bleed in.
        academic_year = batch.academic_year

        # Get all student IDs for bulk querying
        student_ids = [bs.student_id for bs in batch_students]

        # Bulk-load fees data grouped by student (prevent N+1)
        fees_filter = {
            'tenant': school,
            'batch': batch,
            'student_id__in': student_ids,
        }
        if academic_year:
            fees_filter['academic_year'] = academic_year

        fees_by_student = {}
        for row in FinanceFee.objects.filter(**fees_filter).values('student_id').annotate(
            total=Sum('particular_total'),
            balance=Sum('balance')
        ):
            fees_by_student[row['student_id']] = {
                'fees_due': row['total'] or Decimal('0.00'),
                'outstanding_balance': row['balance'] or Decimal('0.00'),
            }

        # Bulk-load payments data grouped by student (prevent N+1)
        payments_filter = {
            'tenant': school,
            'student_id__in': student_ids,
            'category__is_income': True,
        }
        if academic_year:
            payments_filter['academic_year'] = academic_year

        payments_by_student = {}
        for row in FinanceTransaction.objects.filter(**payments_filter).values('student_id').annotate(
            total=Sum('amount')
        ):
            payments_by_student[row['student_id']] = row['total'] or Decimal('0.00')

        # Bulk-load oldest fee date for overdue determination (prevent N+1)
        oldest_fee_by_student = {}
        for row in FinanceFee.objects.filter(
            **fees_filter, balance__gt=0
        ).values('student_id').annotate(
            oldest_date=Min('transaction_date')
        ):
            oldest_fee_by_student[row['student_id']] = row['oldest_date']

        # Bulk-load last payment date (prevent N+1)
        last_payment_by_student = {}
        for row in FinanceTransaction.objects.filter(**payments_filter).values('student_id').annotate(
            latest_date=Max('transaction_date')
        ):
            last_payment_by_student[row['student_id']] = row['latest_date']

        student_fee_data = []
        summary_stats = {
            'total_students': len(batch_students),
            'total_fees_due': Decimal('0.00'),
            'total_collected': Decimal('0.00'),
            'total_outstanding': Decimal('0.00'),
            'paid_in_full_count': 0,
            'partial_payment_count': 0,
            'outstanding_count': 0,
            'overdue_count': 0,
        }

        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now().date() - timedelta(days=30)

        for bs in batch_students:
            student = bs.student

            # Look up pre-computed aggregates (O(1) dictionary lookup, no query)
            fees_due = fees_by_student.get(student.id, {}).get('fees_due', Decimal('0.00'))
            outstanding_fees = fees_by_student.get(student.id, {}).get('outstanding_balance', Decimal('0.00'))
            student_payments = payments_by_student.get(student.id, Decimal('0.00'))
            oldest_fee_date = oldest_fee_by_student.get(student.id)
            last_payment_date = last_payment_by_student.get(student.id)

            # Calculate payment status
            if outstanding_fees <= 0:
                status = 'paid'
                summary_stats['paid_in_full_count'] += 1
            elif student_payments > 0:
                status = 'partial'
                summary_stats['partial_payment_count'] += 1
            else:
                # Check if overdue (more than 30 days since fee date)
                if oldest_fee_date and oldest_fee_date < thirty_days_ago:
                    status = 'overdue'
                    summary_stats['overdue_count'] += 1
                else:
                    status = 'outstanding'
                    summary_stats['outstanding_count'] += 1

            student_fee_info = {
                'student': student,
                'roll_number': bs.roll_number,
                'term_fees_due': fees_due,
                'amount_paid': student_payments,
                'outstanding_balance': outstanding_fees,
                'status': status,
                'last_payment_date': last_payment_date,
            }
            
            # Apply status filter
            if status_filter:
                if status_filter == 'paid' and status != 'paid':
                    continue
                elif status_filter == 'partial' and status != 'partial':
                    continue
                elif status_filter == 'outstanding' and status not in ['outstanding', 'partial']:
                    continue
                elif status_filter == 'overdue' and status != 'overdue':
                    continue
            
            student_fee_data.append(student_fee_info)
            
            # Update summary totals
            summary_stats['total_fees_due'] += fees_due
            summary_stats['total_collected'] += student_payments
            summary_stats['total_outstanding'] += outstanding_fees
        
        return summary_stats, student_fee_data


class FeeReportsView(RedirectView):
    """Deprecated: consolidated into the year-scoped reports hub
    (FeeYearReportsView). Kept only so the existing 'fee_reports' URL name
    keeps working for old bookmarks/links."""
    permanent = False
    query_string = True
    pattern_name = 'core:fee_year_reports'


# API Views for AJAX requests
def student_search_api(request):
    """Search students for fee management, optionally filtered by batch"""
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)

    query = request.GET.get('q', '').strip()
    batch_id = request.GET.get('batch_id', '').strip()

    if len(query) < 2:
        return JsonResponse({'results': []})

    # Start with base query
    student_query = Student.objects.filter(
        tenant=school,
        is_active=True
    ).filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(admission_no__icontains=query)
    )

    # Filter by batch if provided
    if batch_id:
        try:
            batch = Batch.objects.get(id=batch_id, tenant=school)
            student_query = student_query.filter(
                batchstudent__batch=batch,
                batchstudent__is_active=True
            )
        except Batch.DoesNotExist:
            pass

    students = student_query.order_by('first_name', 'last_name')[:10]

    results = []
    for student in students:
        # Get outstanding balance
        outstanding = FinanceFee.objects.filter(
            tenant=school,
            student=student,
            balance__gt=0
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

        results.append({
            'id': str(student.id),
            'name': f"{student.first_name} {student.last_name}",
            'admission_number': student.admission_no,
            'outstanding_balance': float(outstanding)
        })

    return JsonResponse({'results': results})


def batch_students_fees_api(request, batch_id):
    """Get fee information for all students in a batch"""
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    try:
        batch = Batch.objects.get(
            id=batch_id,
            tenant=school,
            is_deleted=False
        )
        
        # Get students in batch with their fee information
        from core.models import BatchStudent
        batch_students = BatchStudent.objects.filter(
            tenant=school,
            batch=batch,
            is_active=True
        ).select_related('student')
        
        student_fees = []
        for bs in batch_students:
            student = bs.student
            outstanding = FinanceFee.objects.filter(
                tenant=school,
                student=student,
                balance__gt=0
            ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
            
            student_fees.append({
                'student_id': str(student.id),
                'name': f"{student.first_name} {student.last_name}",
                'admission_number': student.admission_no,
                'roll_number': bs.roll_number or '',
                'outstanding_balance': float(outstanding)
            })
        
        return JsonResponse({
            'batch_name': batch.name,
            'students': student_fees,
            'total_students': len(student_fees),
            'total_outstanding': sum(s['outstanding_balance'] for s in student_fees)
        })
        
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting batch students fees: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def courses_by_academic_year_api(request):
    """Get courses for a specific academic year"""
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    academic_year_id = request.GET.get('academic_year_id')
    if not academic_year_id:
        return JsonResponse({'error': 'Academic year ID is required'}, status=400)
    
    try:
        from core.models import Course, AcademicYear
        
        # Verify academic year exists and belongs to tenant
        academic_year = AcademicYear.objects.get(
            id=academic_year_id,
            tenant=school,
            is_active=True
        )
        
        # Get all courses that have batches in this academic year
        courses = Course.objects.filter(
            tenant=school,
            is_deleted=False,
            batches__academic_year=academic_year
        ).distinct().order_by('course_name')
        
        course_data = []
        for course in courses:
            course_data.append({
                'id': str(course.id),
                'name': course.course_name,
                'code': course.code,
            })
        
        return JsonResponse({
            'courses': course_data,
            'academic_year': academic_year.name
        })
        
    except AcademicYear.DoesNotExist:
        return JsonResponse({'error': 'Academic year not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting courses by academic year: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def batches_by_course_api(request):
    """Get batches for a specific course and academic year"""
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)
    
    course_id = request.GET.get('course_id')
    academic_year_id = request.GET.get('academic_year_id')
    
    if not course_id or not academic_year_id:
        return JsonResponse({'error': 'Course ID and Academic Year ID are required'}, status=400)
    
    try:
        from core.models import Course, AcademicYear
        
        # Verify course and academic year exist
        course = Course.objects.get(
            id=course_id,
            tenant=school,
            is_deleted=False
        )
        
        academic_year = AcademicYear.objects.get(
            id=academic_year_id,
            tenant=school,
            is_active=True
        )
        
        # Get batches for this course and academic year, with active student
        # counts annotated in one query instead of a COUNT per batch.
        batches = Batch.objects.filter(
            tenant=school,
            course=course,
            academic_year=academic_year,
            is_deleted=False,
            is_active=True
        ).annotate(
            active_students_count=Count(
                'batch_students',
                filter=Q(batch_students__is_active=True),
            )
        ).order_by('name')

        batch_data = []
        for batch in batches:
            batch_data.append({
                'id': str(batch.id),
                'name': batch.name,
                'student_count': batch.active_students_count,
                'start_date': batch.start_date.strftime('%Y-%m-%d') if batch.start_date else None,
                'end_date': batch.end_date.strftime('%Y-%m-%d') if batch.end_date else None,
            })
        
        return JsonResponse({
            'batches': batch_data,
            'course': course.course_name,
            'academic_year': academic_year.name
        })
        
    except Course.DoesNotExist:
        return JsonResponse({'error': 'Course not found'}, status=404)
    except AcademicYear.DoesNotExist:
        return JsonResponse({'error': 'Academic year not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting batches by course: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def batch_students_for_collection_api(request, batch_id):
    """Get students in a batch for fee collection page filtering"""
    school = getattr(request, 'tenant', None)
    if not school:
        return JsonResponse({'error': 'School not found'}, status=400)

    try:
        batch = Batch.objects.get(
            id=batch_id,
            tenant=school,
            is_deleted=False
        )

        batch_students = BatchStudent.objects.filter(
            tenant=school,
            batch=batch,
            is_active=True
        ).select_related('student').order_by('student__first_name', 'student__last_name')

        students = []
        for bs in batch_students:
            student = bs.student
            outstanding = FinanceFee.objects.filter(
                tenant=school,
                student=student,
                balance__gt=0
            ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

            students.append({
                'id': str(student.id),
                'name': f"{student.first_name} {student.last_name}",
                'admission_number': student.admission_no,
                'outstanding_balance': float(outstanding)
            })

        return JsonResponse({'students': students})

    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting batch students: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


class FeeParticularsView(TemplateView):
    """Fee Particulars management page"""
    template_name = 'core/fees/particulars.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        from core.models import FeeParticular, FeeCategory, AcademicYear, FineSlab

        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(
            tenant=school,
            is_active=True
        ).first()

        # Get fee categories for current academic year
        fee_categories = FeeCategory.objects.filter(
            tenant=school,
            is_deleted=False,
            academic_year=current_academic_year
        ).order_by('name')

        # Get existing particulars
        particulars = FeeParticular.objects.filter(
            tenant=school,
            is_active=True
        ).select_related('fee_category', 'fine_slab').order_by('-created_at')

        fine_slab_names = FineSlab.objects.filter(
            tenant=school, is_active=True
        ).values_list('fine_name', flat=True).distinct().order_by('fine_name')

        # Get master particulars
        from core.services.finance_service import FinanceService
        finance_service = FinanceService(school)
        master_particulars = finance_service.list_master_particulars(is_active=True)

        context.update({
            'school': school,
            'fee_categories': fee_categories,
            'particulars': particulars,
            'current_academic_year': current_academic_year,
            'fine_slab_names': fine_slab_names,
            'master_particulars': master_particulars,
            'back_url': self.request.GET.get('back', reverse('core:fee_structure')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Fee Structure', 'url': reverse('core:fee_structure')},
                {'label': 'Particulars'},
            ],
        })

        return context


class FeeParticularsCreateView(View):
    """Create, update, or delete a fee particular"""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        action = request.POST.get('action', 'create')

        try:
            if action == 'update':
                return self._update(request, school)
            elif action == 'delete':
                return self._delete(request, school)
            else:
                return self._create(request, school)
        except Exception as e:
            logger.error(f"Error in fee particular POST: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    def _parse_and_validate(self, request, school, exclude_particular_id=None):
        """Shared parsing/validation for create and update. Returns either
        (fields_dict, fee_category, fine_slab, None) or (None, None, None, error_response)."""
        from core.models import FeeParticular, FeeCategory, FineSlab
        from django.utils.dateparse import parse_date

        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        fee_category_id = request.POST.get('fee_category')
        amount = request.POST.get('amount', '').strip()
        due_date = parse_date(request.POST.get('due_date', '').strip()) or None
        fine_slab_name = request.POST.get('fine_slab', '').strip() or None

        if not all([name, fee_category_id, amount]):
            return None, None, None, JsonResponse({
                'error': 'Name, fee category, and amount are required'
            }, status=400)

        try:
            amount = float(amount)
            if amount < 0:
                return None, None, None, JsonResponse({
                    'error': 'Amount must be positive'
                }, status=400)
        except ValueError:
            return None, None, None, JsonResponse({
                'error': 'Invalid amount value'
            }, status=400)

        fee_category = get_object_or_404(FeeCategory, pk=fee_category_id, tenant=school)

        duplicates = FeeParticular.objects.filter(
            tenant=school, name=name, fee_category=fee_category, is_active=True
        )
        if exclude_particular_id:
            duplicates = duplicates.exclude(id=exclude_particular_id)
        if duplicates.exists():
            return None, None, None, JsonResponse({
                'error': 'Fee particular with this name already exists for this category'
            }, status=400)

        fine_slab = None
        if fine_slab_name:
            fine_slab = FineSlab.objects.filter(
                tenant=school, fine_name=fine_slab_name, is_active=True
            ).order_by('days_after_due').first()

        fields = {
            'name': name,
            'description': description,
            'amount': amount,
            'due_date': due_date,
            'fine_slab': fine_slab,
        }
        return fields, fee_category, fine_slab, None

    def _create(self, request, school):
        from core.services.finance_service import FinanceService
        from core.services.exceptions import ValidationException, NotFoundException, DuplicateException

        try:
            fields, fee_category, fine_slab, error_response = self._parse_and_validate(request, school)
            if error_response:
                return error_response

            particular = FinanceService(school).upsert_fee_particular(
                fee_category_id=fee_category.id,
                **fields,
            )

            return JsonResponse({
                'success': True,
                'message': 'Fee particular created successfully',
                'particular': {
                    'id': particular.id,
                    'name': particular.name,
                    'amount': float(particular.amount),
                    'fee_category': particular.fee_category.name,
                    'due_date': particular.due_date.isoformat() if particular.due_date else None,
                }
            })
        except (ValidationException, NotFoundException, DuplicateException) as e:
            return JsonResponse({'error': str(e)}, status=400)

    def _update(self, request, school):
        from core.services.finance_service import FinanceService
        from core.services.exceptions import ValidationException, NotFoundException, DuplicateException

        particular_id = request.POST.get('particular_id')
        if not particular_id:
            return JsonResponse({'error': 'Particular ID is required'}, status=400)

        try:
            fields, fee_category, fine_slab, error_response = self._parse_and_validate(
                request, school, exclude_particular_id=particular_id
            )
            if error_response:
                return error_response

            particular = FinanceService(school).upsert_fee_particular(
                fee_category_id=fee_category.id,
                particular_id=particular_id,
                user=request.user,
                **fields,
            )

            return JsonResponse({
                'success': True,
                'message': 'Fee particular updated successfully',
                'particular': {
                    'id': particular.id,
                    'name': particular.name,
                    'amount': float(particular.amount),
                    'fee_category': particular.fee_category.name,
                    'due_date': particular.due_date.isoformat() if particular.due_date else None,
                }
            })
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except (ValidationException, DuplicateException) as e:
            return JsonResponse({'error': str(e)}, status=400)

    def _delete(self, request, school):
        from core.services.finance_service import FinanceService
        from core.services.exceptions import NotFoundException, BusinessLogicException

        particular_id = request.POST.get('particular_id')
        if not particular_id:
            return JsonResponse({'error': 'Particular ID is required'}, status=400)

        try:
            FinanceService(school).delete_fee_particular(particular_id)
            return JsonResponse({
                'success': True,
                'message': 'Fee particular deleted successfully'
            })
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except BusinessLogicException as e:
            return JsonResponse({'error': str(e)}, status=400)


class FeeDiscountsView(TemplateView):
    """Fee Discounts management page"""
    template_name = 'core/fees/discounts.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        from core.models import FeeDiscount, FeeCategory, AcademicYear, Batch
        
        # Get current academic year
        current_academic_year = AcademicYear.objects.filter(
            tenant=school,
            is_active=True
        ).first()
        
        # Get fee categories for current academic year
        fee_categories = FeeCategory.objects.filter(
            tenant=school,
            is_deleted=False,
            academic_year=current_academic_year
        ).order_by('name')
        
        # Get batches
        batches = Batch.objects.filter(
            tenant=school,
            is_deleted=False
        ).select_related('course').order_by('course__name', 'name')
        
        # Get existing discounts
        discounts = FeeDiscount.objects.filter(
            tenant=school,
            is_active=True
        ).select_related('fee_category').order_by('-created_at')
        
        context.update({
            'school': school,
            'fee_categories': fee_categories,
            'batches': batches,
            'discounts': discounts,
            'current_academic_year': current_academic_year,
            'back_url': self.request.GET.get('back', reverse('core:fee_structure')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Fee Structure', 'url': reverse('core:fee_structure')},
                {'label': 'Discounts'},
            ],
        })

        return context


class FeeDiscountsCreateView(View):
    """Create new fee discount"""
    
    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            from core.models import FeeDiscount, FeeCategory, Batch
            
            name = request.POST.get('name', '').strip()
            discount_type = request.POST.get('discount_type', 'batch')
            fee_category_id = request.POST.get('fee_category')
            discount_mode = request.POST.get('discount_mode', 'percentage')
            discount_value = request.POST.get('discount_value', '').strip()
            
            # Validation
            if not all([name, fee_category_id, discount_value]):
                return JsonResponse({
                    'error': 'Name, fee category, and discount value are required'
                }, status=400)
            
            try:
                discount_value = float(discount_value)
                if discount_value < 0:
                    return JsonResponse({
                        'error': 'Discount value must be positive'
                    }, status=400)
                
                if discount_mode == 'percentage' and discount_value > 100:
                    return JsonResponse({
                        'error': 'Percentage discount cannot exceed 100%'
                    }, status=400)
            except ValueError:
                return JsonResponse({
                    'error': 'Invalid discount value'
                }, status=400)
            
            fee_category = get_object_or_404(FeeCategory, pk=fee_category_id, tenant=school)
            
            # Check for duplicates
            if FeeDiscount.objects.filter(
                tenant=school,
                name=name,
                fee_category=fee_category,
                is_active=True
            ).exists():
                return JsonResponse({
                    'error': 'Discount with this name already exists for this category'
                }, status=400)
            
            # Create discount
            discount = FeeDiscount.objects.create(
                tenant=school,
                name=name,
                discount_type=discount_type,
                fee_category=fee_category,
                discount_mode=discount_mode,
                discount_value=discount_value
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Fee discount created successfully',
                'discount': {
                    'id': discount.id,
                    'name': discount.name,
                    'discount_type': discount.discount_type,
                    'discount_mode': discount.discount_mode,
                    'discount_value': float(discount.discount_value),
                    'fee_category': discount.fee_category.name
                }
            })
            
        except Exception as e:
            logger.error(f"Error creating fee discount: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class AddStudentParticularView(View):
    """Add a one-time particular (extra charge) to a student"""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            student_id = request.POST.get('student_id')
            master_particular_id = request.POST.get('master_particular_id')
            amount_str = request.POST.get('amount')
            description = request.POST.get('description', '').strip()
            academic_year_id = request.POST.get('academic_year_id')

            if not all([student_id, master_particular_id, amount_str]):
                return JsonResponse({'error': 'All fields are required'}, status=400)

            try:
                amount = Decimal(amount_str)
                if amount <= 0:
                    return JsonResponse({'error': 'Amount must be positive'}, status=400)
            except (ValueError, InvalidOperation):
                return JsonResponse({'error': 'Invalid amount'}, status=400)

            student = Student.objects.filter(
                id=student_id, tenant=school, is_active=True
            ).first()
            if not student:
                return JsonResponse({'error': 'Student not found'}, status=404)

            master_particular = FeeMasterParticular.objects.filter(
                id=master_particular_id, tenant=school, is_active=True
            ).first()
            if not master_particular:
                return JsonResponse({'error': 'Fee particular not found'}, status=404)

            # Resolve the fee category to file the new particular under —
            # prefer a category the student already has an outstanding
            # balance in, falling back to their batch's assigned category.
            outstanding_fee = FinanceFee.objects.filter(
                tenant=school, student=student, balance__gt=0
            ).select_related('fee_category').order_by('-transaction_date').first()
            fee_category = outstanding_fee.fee_category if outstanding_fee else None

            if not fee_category:
                current_batch = BatchStudent.objects.filter(
                    tenant=school, student=student, is_active=True
                ).select_related('batch').first()
                batch_fee_category = None
                if current_batch:
                    batch_fee_category = BatchFeeCategory.objects.filter(
                        tenant=school, batch=current_batch.batch
                    ).select_related('fee_category').first()
                fee_category = batch_fee_category.fee_category if batch_fee_category else None

            if not fee_category:
                return JsonResponse({
                    'error': "Could not determine a fee category for this student. "
                             "Assign one under Fee Structure before adding a particular."
                }, status=400)

            # Reuse the existing particular for this master/category pair
            # rather than creating a duplicate; keep its price current.
            particular = FeeParticular.objects.filter(
                tenant=school, fee_category=fee_category,
                master_particular=master_particular, is_active=True,
            ).first()
            if particular:
                particular.amount = amount
                if description:
                    particular.description = description
                particular.save(update_fields=['amount', 'description', 'updated_at'])
            else:
                particular = FeeParticular.objects.create(
                    tenant=school,
                    name=master_particular.name,
                    fee_category=fee_category,
                    master_particular=master_particular,
                    amount=amount,
                    description=description,
                    is_active=True,
                )

            academic_year = None
            if academic_year_id:
                academic_year = AcademicYear.objects.filter(
                    id=academic_year_id, tenant=school
                ).first()

            finance_service = FinanceService(school)
            if academic_year is None:
                academic_year = finance_service.get_active_academic_year()

            fee = finance_service.record_student_fee(
                student_id=str(student.id),
                fee_category_id=str(fee_category.id),
                balance=amount,
                academic_year=academic_year,
                transaction_date=date.today()
            )

            # Log transaction. reference_number links this ledger row back to
            # the FinanceFee it created, so it can be identified for removal
            # later (see RemoveStudentChargeView) while it's still untouched
            # by any payment/discount/fine.
            FeeTransaction.objects.create(
                tenant=school,
                student=student,
                fee_category=fee_category,
                fee_particular=particular,
                academic_year=academic_year,
                transaction_type='charge',
                amount=amount,
                reference_number=f"CHARGE:{fee.id}",
                description=description or f"One-time charge: {master_particular.name}"
            )

            return JsonResponse({
                'success': True,
                'message': f'Charge of {amount} added to {student.first_name} {student.last_name}',
                'fee_id': str(fee.id),
                'amount': float(amount)
            })

        except (ValidationException, NotFoundException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error adding student particular: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class RemoveStudentChargeView(View):
    """Undo a one-time particular charge added via AddStudentParticularView,
    as long as no payment/discount/fine has touched it yet."""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        fee_transaction_id = request.POST.get('fee_transaction_id')
        reason = request.POST.get('reason', '').strip()
        if not fee_transaction_id:
            return JsonResponse({'error': 'Charge reference is required'}, status=400)

        try:
            FinanceService(school).remove_student_charge(
                fee_transaction_id, reason=reason, user=getattr(request, 'user', None),
            )
            return JsonResponse({'success': True, 'message': 'Charge removed successfully'})
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except (BusinessLogicException, ValidationException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error removing student charge: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class AddStudentDiscountView(View):
    """Apply a discount to a student's fee"""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            student_id = request.POST.get('student_id')
            fee_category_id = request.POST.get('fee_category_id')
            discount_id = request.POST.get('discount_id')
            amount_str = request.POST.get('amount')
            academic_year_id = request.POST.get('academic_year_id')

            if not all([student_id, fee_category_id, discount_id]):
                return JsonResponse({'error': 'All fields are required'}, status=400)

            student = Student.objects.filter(
                id=student_id, tenant=school, is_active=True
            ).first()
            if not student:
                return JsonResponse({'error': 'Student not found'}, status=404)

            fee_category = FeeCategory.objects.filter(
                id=fee_category_id, tenant=school, is_deleted=False
            ).first()
            if not fee_category:
                return JsonResponse({'error': 'Fee category not found'}, status=404)

            discount = FeeDiscount.objects.filter(
                id=discount_id, tenant=school, is_active=True
            ).first()
            if not discount:
                return JsonResponse({'error': 'Discount not found'}, status=404)

            academic_year = None
            if academic_year_id:
                academic_year = AcademicYear.objects.filter(
                    id=academic_year_id, tenant=school
                ).first()

            finance_service = FinanceService(school)
            if academic_year is None:
                academic_year = finance_service.get_active_academic_year()

            # Parse amount if provided (for partial discount)
            base_amount = None
            if amount_str:
                try:
                    base_amount = Decimal(amount_str)
                except (ValueError, InvalidOperation):
                    return JsonResponse({'error': 'Invalid amount'}, status=400)

            fee, discount_amount = finance_service.apply_discount(
                student=student,
                fee_category=fee_category,
                discount=discount,
                base_amount=base_amount,
                academic_year=academic_year
            )

            return JsonResponse({
                'success': True,
                'message': f'Discount of {discount_amount} applied to {student.first_name} {student.last_name}',
                'discount_amount': float(discount_amount),
                'new_balance': float(fee.balance)
            })

        except (ValidationException, NotFoundException, BusinessLogicException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error applying student discount: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class AddStudentFineView(View):
    """Apply a fine to a student's fee"""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            student_id = request.POST.get('student_id')
            fee_category_id = request.POST.get('fee_category_id')
            fine_slab_id = request.POST.get('fine_slab_id')
            academic_year_id = request.POST.get('academic_year_id')

            if not all([student_id, fee_category_id, fine_slab_id]):
                return JsonResponse({'error': 'All fields are required'}, status=400)

            student = Student.objects.filter(
                id=student_id, tenant=school, is_active=True
            ).first()
            if not student:
                return JsonResponse({'error': 'Student not found'}, status=404)

            fee_category = FeeCategory.objects.filter(
                id=fee_category_id, tenant=school, is_deleted=False
            ).first()
            if not fee_category:
                return JsonResponse({'error': 'Fee category not found'}, status=404)

            fine_slab = FineSlab.objects.filter(
                id=fine_slab_id, tenant=school, is_active=True
            ).first()
            if not fine_slab:
                return JsonResponse({'error': 'Fine slab not found'}, status=404)

            academic_year = None
            if academic_year_id:
                academic_year = AcademicYear.objects.filter(
                    id=academic_year_id, tenant=school
                ).first()

            finance_service = FinanceService(school)
            if academic_year is None:
                academic_year = finance_service.get_active_academic_year()

            fee, fine_amount = finance_service.apply_fine(
                student=student,
                fee_category=fee_category,
                fine_slab=fine_slab,
                academic_year=academic_year
            )

            return JsonResponse({
                'success': True,
                'message': f'Fine of {fine_amount} applied to {student.first_name} {student.last_name}',
                'fine_amount': float(fine_amount),
                'new_balance': float(fee.balance) if fee else 0
            })

        except (ValidationException, NotFoundException, BusinessLogicException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error applying student fine: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FeeWaiversListView(TemplateView):
    """Fee Waivers/Scholarships management page: browse granted waivers and
    revoke them. Creation is still handled by GrantWaiverView (reused as-is,
    routed under a new URL) - this screen adds the missing list/revoke UI."""
    template_name = 'core/fees/waivers.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        from core.models import FeeWaiver, FeeCategory, AcademicYear

        current_academic_year = AcademicYear.objects.filter(
            tenant=school, is_active=True
        ).first()

        fee_categories = FeeCategory.objects.filter(
            tenant=school, is_deleted=False
        ).order_by('name')

        waivers = FeeWaiver.objects.filter(
            tenant=school
        ).select_related('student', 'fee_category', 'academic_year', 'approved_by').order_by('-approval_date')

        waiver_type = self.request.GET.get('waiver_type')
        if waiver_type:
            waivers = waivers.filter(waiver_type=waiver_type)

        status = self.request.GET.get('status', 'active')
        if status == 'active':
            waivers = waivers.filter(is_active=True)
        elif status == 'revoked':
            waivers = waivers.filter(is_active=False)

        context.update({
            'school': school,
            'fee_categories': fee_categories,
            'current_academic_year': current_academic_year,
            'waivers': waivers,
            'waiver_type_filter': waiver_type or '',
            'status_filter': status,
            'back_url': self.request.GET.get('back', reverse('core:fee_structure')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Fee Structure', 'url': reverse('core:fee_structure')},
                {'label': 'Waivers'},
            ],
        })
        return context


class FeeWaiverRevokeView(View):
    """Revoke a previously granted waiver (compensating entry; preserves history)."""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        waiver_id = request.POST.get('waiver_id')
        reason = request.POST.get('reason', '').strip()
        if not waiver_id:
            return JsonResponse({'error': 'Waiver is required'}, status=400)

        try:
            waiver, fee = FinanceService(school).revoke_waiver(
                waiver_id, reason=reason, user=getattr(request, 'user', None),
            )
            return JsonResponse({
                'success': True,
                'message': 'Waiver revoked successfully',
                'restored_balance': float(fee.balance),
            })
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except (BusinessLogicException, ValidationException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error revoking waiver: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FineSlabsView(TemplateView):
    """Fine Slabs management page"""
    template_name = 'core/fees/fine_slabs.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        
        from core.models import FineSlab
        
        # Get existing fine slabs
        fine_slabs = FineSlab.objects.filter(
            tenant=school,
            is_active=True
        ).order_by('fine_name', 'days_after_due')
        
        # Group by fine name
        grouped_slabs = {}
        for slab in fine_slabs:
            if slab.fine_name not in grouped_slabs:
                grouped_slabs[slab.fine_name] = []
            grouped_slabs[slab.fine_name].append(slab)
        
        context.update({
            'school': school,
            'fine_slabs': fine_slabs,
            'grouped_slabs': grouped_slabs,
            'back_url': self.request.GET.get('back', reverse('core:fee_structure')),
            'crumbs': [
                {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
                {'label': 'Fee Structure', 'url': reverse('core:fee_structure')},
                {'label': 'Fine Slabs'},
            ],
        })

        return context


class FineSlabsCreateView(View):
    """Create new fine slab"""
    
    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)
        
        try:
            from core.models import FineSlab
            
            fine_name = request.POST.get('fine_name', '').strip()
            days_after_due = request.POST.get('days_after_due', '').strip()
            fine_mode = request.POST.get('fine_mode', 'percentage')
            fine_value = request.POST.get('fine_value', '').strip()
            
            # Validation
            if not all([fine_name, days_after_due, fine_value]):
                return JsonResponse({
                    'error': 'Fine name, days after due, and fine value are required'
                }, status=400)
            
            try:
                days_after_due = int(days_after_due)
                if days_after_due < 0:
                    return JsonResponse({
                        'error': 'Days after due must be positive'
                    }, status=400)
            except ValueError:
                return JsonResponse({
                    'error': 'Invalid days after due value'
                }, status=400)
            
            try:
                fine_value = float(fine_value)
                if fine_value < 0:
                    return JsonResponse({
                        'error': 'Fine value must be positive'
                    }, status=400)
            except ValueError:
                return JsonResponse({
                    'error': 'Invalid fine value'
                }, status=400)
            
            # Check for duplicate slab
            if FineSlab.objects.filter(
                tenant=school,
                fine_name=fine_name,
                days_after_due=days_after_due,
                is_active=True
            ).exists():
                return JsonResponse({
                    'error': 'Fine slab already exists for this fine name and days after due'
                }, status=400)
            
            # Create fine slab
            fine_slab = FineSlab.objects.create(
                tenant=school,
                fine_name=fine_name,
                days_after_due=days_after_due,
                fine_mode=fine_mode,
                fine_value=fine_value
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Fine slab created successfully',
                'fine_slab': {
                    'id': fine_slab.id,
                    'fine_name': fine_slab.fine_name,
                    'days_after_due': fine_slab.days_after_due,
                    'fine_mode': fine_slab.fine_mode,
                    'fine_value': float(fine_slab.fine_value)
                }
            })
            
        except Exception as e:
            logger.error(f"Error creating fine slab: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class QuickBooksFeePaymentView(View):
    """Deprecated thin wrapper. Fee payments now go through the single
    consolidated path (FinanceService.create_fee_payment), which records the
    year-scoped ledger AND enqueues the QuickBooks invoice/payment sync after
    commit (backend Phase 7). This endpoint is retained for backward
    compatibility and simply delegates to that path."""

    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)

        try:
            student_id = request.POST.get('student_id')
            amount = request.POST.get('amount')
            payment_method = request.POST.get('payment_method', 'cash')
            fee_category_id = request.POST.get('fee_category_id')
            academic_year_id = request.POST.get('academic_year')
            reference_number = request.POST.get('reference_number', '').strip() or None

            if not all([student_id, amount, fee_category_id]):
                return JsonResponse({'error': 'Student ID, amount, and fee category are required'}, status=400)

            try:
                amount = Decimal(amount)
                if amount <= 0:
                    return JsonResponse({'error': 'Amount must be positive'}, status=400)
            except (ValueError, InvalidOperation):
                return JsonResponse({'error': 'Invalid amount'}, status=400)

            student = Student.objects.filter(id=student_id, tenant=school).first()
            fee_category = FeeCategory.objects.filter(id=fee_category_id, tenant=school).first()
            if not student or not fee_category:
                return JsonResponse({'error': 'Student or fee category not found'}, status=404)

            academic_year = None
            if academic_year_id:
                academic_year = AcademicYear.objects.filter(id=academic_year_id, tenant=school).first()

            finance_service = FinanceService(school)
            with transaction.atomic():
                fee_transaction = finance_service.create_fee_payment(
                    student=student, amount=amount, payment_method=payment_method,
                    fee_category=fee_category, academic_year=academic_year,
                    reference_number=reference_number,
                )

            return JsonResponse({
                'success': True,
                'message': 'Fee payment processed successfully. QuickBooks sync (if connected) runs in the background.',
                'fee_transaction': {'id': str(fee_transaction.id), 'amount': float(amount)},
            })
        except (BusinessLogicException, DuplicateException, ValidationException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error processing fee payment: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class QuickBooksStudentSyncView(View):
    """Sync student as customer to QuickBooks"""
    
    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)
        
        try:
            student_id = request.POST.get('student_id')
            if not student_id:
                return JsonResponse({'error': 'Student ID is required'}, status=400)
            
            try:
                student = Student.objects.get(id=student_id, tenant=school)
            except Student.DoesNotExist:
                return JsonResponse({'error': 'Student not found'}, status=404)
            
            # Check QuickBooks connection
            qb_service = QuickBooksService(school)
            connection_status = qb_service.get_connection_status()
            
            if not connection_status.get('connected', False):
                return JsonResponse({
                    'error': 'QuickBooks not connected',
                    'quickbooks_status': connection_status
                }, status=400)
            
            # Sync student as customer
            qb_sync_service = QuickBooksFeeSync(school)
            sync_result = qb_sync_service.sync_student_as_customer(student)
            
            return JsonResponse({
                'success': True,
                'message': f'Student {student.first_name} {student.last_name} synced successfully',
                'quickbooks_customer_id': sync_result.get('quickbooks_customer_id'),
                'sync_status': sync_result.get('sync_status')
            })
            
        except Exception as e:
            logger.error(f"Error syncing student to QuickBooks: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class QuickBooksBulkStudentSyncView(View):
    """Bulk sync students as customers to QuickBooks"""
    
    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)
        
        try:
            batch_id = request.POST.get('batch_id')
            # Syncing the entire school is a heavy, rate-limit-prone operation.
            # Require either a batch_id or an explicit confirm_all flag.
            confirm_all = request.POST.get('confirm_all', 'false').lower() in ('true', 'on', '1')

            if batch_id:
                try:
                    batch = Batch.objects.get(id=batch_id, tenant=school)
                    students = Student.objects.filter(
                        batchstudent__batch=batch,
                        batchstudent__is_active=True,
                        tenant=school,
                        is_active=True,
                    ).distinct()
                except Batch.DoesNotExist:
                    return JsonResponse({'error': 'Batch not found'}, status=404)
            else:
                if not confirm_all:
                    return JsonResponse({
                        'error': 'Syncing all students is a large operation. Provide a batch_id, '
                                 'or resend with confirm_all=true to sync the entire school.',
                        'requires_confirmation': True,
                    }, status=400)
                students = Student.objects.filter(tenant=school, is_active=True)

            # Check QuickBooks connection
            qb_service = QuickBooksService(school)
            connection_status = qb_service.get_connection_status()
            
            if not connection_status.get('connected', False):
                return JsonResponse({
                    'error': 'QuickBooks not connected',
                    'quickbooks_status': connection_status
                }, status=400)
            
            # Bulk sync students
            qb_sync_service = QuickBooksFeeSync(school)
            sync_results = qb_sync_service.bulk_sync_students_as_customers(students.all())
            
            return JsonResponse({
                'success': True,
                'message': f'Bulk sync completed for {len(sync_results["successful"])} students',
                'results': sync_results
            })
            
        except Exception as e:
            logger.error(f"Error in bulk student sync: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class QuickBooksReceiptReconciliationView(View):
    """View to reconcile payment receipts between local and QuickBooks"""
    
    def get(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)
        
        try:
            # Get payment sync records
            payment_syncs = QuickBooksFeePaymentSync.objects.filter(
                tenant=school,
                sync_status__in=['synced', 'error']
            ).order_by('-payment_date')[:50]
            
            reconciliation_data = []
            for sync in payment_syncs:
                reconciliation_data.append({
                    'id': str(sync.id),
                    'student_name': f"{sync.student.first_name} {sync.student.last_name}",
                    'amount': float(sync.amount),
                    'payment_date': sync.payment_date.isoformat(),
                    'receipt_number': sync.receipt_number,
                    'quickbooks_payment_id': sync.quickbooks_payment_id,
                    'sync_status': sync.sync_status,
                    'error_message': sync.error_message,
                    'created_at': sync.created_at.isoformat()
                })
            
            return JsonResponse({
                'success': True,
                'reconciliation_data': reconciliation_data
            })
            
        except Exception as e:
            logger.error(f"Error retrieving reconciliation data: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def post(self, request):
        """Reconcile specific payment with QuickBooks"""
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)
        
        try:
            payment_sync_id = request.POST.get('payment_sync_id')
            if not payment_sync_id:
                return JsonResponse({'error': 'Payment sync ID is required'}, status=400)
            
            try:
                payment_sync = QuickBooksFeePaymentSync.objects.get(
                    id=payment_sync_id,
                    tenant=school
                )
            except QuickBooksFeePaymentSync.DoesNotExist:
                return JsonResponse({'error': 'Payment sync record not found'}, status=404)
            
            # Check QuickBooks connection
            qb_service = QuickBooksService(school)
            connection_status = qb_service.get_connection_status()
            
            if not connection_status.get('connected', False):
                return JsonResponse({
                    'error': 'QuickBooks not connected',
                    'quickbooks_status': connection_status
                }, status=400)
            
            # Reconcile payment
            qb_sync_service = QuickBooksFeeSync(school)
            reconcile_result = qb_sync_service.reconcile_payments([payment_sync])
            
            return JsonResponse({
                'success': True,
                'message': 'Payment reconciliation completed',
                'result': reconcile_result
            })
            
        except Exception as e:
            logger.error(f"Error reconciling payment: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FeeMastersView(TemplateView):
    """List master particulars and master discounts"""
    template_name = 'core/fees/fee_masters.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        finance_service = FinanceService(school)
        context['master_particulars'] = finance_service.list_master_particulars(is_active=None)
        context['master_discounts'] = finance_service.list_master_discounts(is_active=None)
        context['applicability_rules'] = finance_service.list_applicability_rules(is_active=None)
        context['student_categories'] = StudentCategory.objects.filter(tenant=school).order_by('name')
        context['batches'] = Batch.objects.filter(tenant=school).order_by('name')
        context['students'] = Student.objects.filter(tenant=school).order_by('first_name', 'last_name')
        context['particular_columns'] = ['Name', 'Description', 'Status', 'Used In', 'Actions']
        context['discount_columns'] = ['Name', 'Type', 'Value', 'Description', 'Status', 'Used In', 'Actions']
        context['rule_columns'] = ['Rule Type', 'Applies To', 'Status', 'Actions']
        context['particular_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Save Particular', 'variant': 'primary', 'type': 'submit', 'icon': 'fa-save'},
        ]
        context['discount_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Save Discount', 'variant': 'primary', 'type': 'submit', 'icon': 'fa-save'},
        ]
        context['rule_footer'] = [
            {'label': 'Cancel', 'variant': 'outline', 'attrs': 'data-bs-dismiss="modal"'},
            {'label': 'Save Rule', 'variant': 'primary', 'type': 'submit', 'icon': 'fa-save'},
        ]
        return context


class FeeMasterParticularSaveView(View):
    """Create or update a master particular"""

    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)

        try:
            data = json.loads(request.body)
            master_id = data.get('id')
            name = data.get('name', '').strip()
            description = data.get('description', '').strip()
            is_active = data.get('is_active', True)

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)

            finance_service = FinanceService(school)

            if master_id:
                # Update
                master = finance_service.update_master_particular(
                    master_id, name=name, description=description, is_active=is_active
                )
                message = 'Master particular updated successfully'
            else:
                # Create
                master = finance_service.create_master_particular(name, description, is_active)
                message = 'Master particular created successfully'

            return JsonResponse({
                'success': True,
                'message': message,
                'id': str(master.id) if master is not None else master_id,
                'name': name,
            })
        except DuplicateException as e:
            return JsonResponse({'error': str(e)}, status=409)
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error saving master particular: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FeeMasterParticularDeleteView(View):
    """Delete a master particular"""

    def post(self, request, pk):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)

        try:
            finance_service = FinanceService(school)
            finance_service.delete_master_particular(pk)
            return JsonResponse({'success': True, 'message': 'Master particular deleted successfully'})
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except Exception as e:
            logger.error(f"Error deleting master particular: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FeeMasterDiscountSaveView(View):
    """Create or update a master discount"""

    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)

        try:
            data = json.loads(request.body)
            master_id = data.get('id')
            name = data.get('name', '').strip()
            discount_type = data.get('discount_type', '').strip()
            value = data.get('value')
            description = data.get('description', '').strip()
            is_active = data.get('is_active', True)

            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            if not discount_type or discount_type not in ['percentage', 'fixed']:
                return JsonResponse({'error': 'Discount type must be percentage or fixed'}, status=400)
            if value is None:
                return JsonResponse({'error': 'Value is required'}, status=400)

            try:
                value = Decimal(str(value))
            except (InvalidOperation, TypeError):
                return JsonResponse({'error': 'Value must be a valid number'}, status=400)

            if value < 0:
                return JsonResponse({'error': 'Value must be non-negative'}, status=400)

            finance_service = FinanceService(school)

            if master_id:
                # Update
                finance_service.update_master_discount(
                    master_id, name=name, discount_type=discount_type, value=value,
                    description=description, is_active=is_active
                )
                message = 'Master discount updated successfully'
            else:
                # Create
                finance_service.create_master_discount(name, discount_type, value, description, is_active)
                message = 'Master discount created successfully'

            return JsonResponse({'success': True, 'message': message})
        except DuplicateException as e:
            return JsonResponse({'error': str(e)}, status=409)
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error saving master discount: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FeeMasterDiscountDeleteView(View):
    """Delete a master discount"""

    def post(self, request, pk):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)

        try:
            finance_service = FinanceService(school)
            finance_service.delete_master_discount(pk)
            return JsonResponse({'success': True, 'message': 'Master discount deleted successfully'})
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except Exception as e:
            logger.error(f"Error deleting master discount: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FeeApplicabilityRuleSaveView(View):
    """Create or update an applicability rule"""

    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)

        try:
            data = json.loads(request.body)
            rule_id = data.get('id')
            rule_type = data.get('rule_type', '').strip()
            is_active = data.get('is_active', True)

            if not rule_type or rule_type not in ['all', 'admission_number', 'student_category', 'batch', 'individual_student']:
                return JsonResponse({'error': 'Invalid rule_type'}, status=400)

            finance_service = FinanceService(school)

            fields = {'rule_type': rule_type, 'is_active': is_active}

            if rule_type == 'admission_number':
                admission_number = data.get('admission_number', '').strip()
                if not admission_number:
                    return JsonResponse({'error': 'Admission number is required'}, status=400)
                fields['admission_number'] = admission_number
                fields['student_category_id'] = None
                fields['batch_id'] = None
                fields['student_id'] = None
            elif rule_type == 'student_category':
                student_category_id = data.get('student_category_id')
                if not student_category_id:
                    return JsonResponse({'error': 'Student category is required'}, status=400)
                fields['student_category_id'] = student_category_id
                fields['admission_number'] = None
                fields['batch_id'] = None
                fields['student_id'] = None
            elif rule_type == 'batch':
                batch_id = data.get('batch_id')
                if not batch_id:
                    return JsonResponse({'error': 'Batch is required'}, status=400)
                fields['batch_id'] = batch_id
                fields['admission_number'] = None
                fields['student_category_id'] = None
                fields['student_id'] = None
            elif rule_type == 'individual_student':
                student_id = data.get('student_id')
                if not student_id:
                    return JsonResponse({'error': 'Student is required'}, status=400)
                fields['student_id'] = student_id
                fields['admission_number'] = None
                fields['student_category_id'] = None
                fields['batch_id'] = None
            else:
                fields['admission_number'] = None
                fields['student_category_id'] = None
                fields['batch_id'] = None
                fields['student_id'] = None

            if rule_id:
                finance_service.update_applicability_rule(rule_id, **fields)
                message = 'Applicability rule updated successfully'
            else:
                finance_service.create_applicability_rule(**fields)
                message = 'Applicability rule created successfully'

            return JsonResponse({'success': True, 'message': message})
        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error saving applicability rule: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FeeApplicabilityRuleDeleteView(View):
    """Delete an applicability rule"""

    def post(self, request, pk):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)

        try:
            finance_service = FinanceService(school)
            finance_service.delete_applicability_rule(pk)
            return JsonResponse({'success': True, 'message': 'Applicability rule deleted successfully'})
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except Exception as e:
            logger.error(f"Error deleting applicability rule: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FeeMasterParticularUsageView(View):
    """Get list of fee particulars linked to a master particular"""

    def get(self, request, pk):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)

        try:
            finance_service = FinanceService(school)
            particulars = finance_service.get_base_queryset(FeeParticular).filter(
                master_particular_id=pk
            ).select_related('fee_category').values('id', 'name', 'fee_category__name', 'amount')

            items = [
                {
                    'id': str(p['id']),
                    'name': p['name'],
                    'fee_category': p['fee_category__name'],
                    'amount': str(p['amount'])
                }
                for p in particulars
            ]
            return JsonResponse({'items': items})
        except Exception as e:
            logger.error(f"Error fetching master particular usage: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


class FeeMasterDiscountUsageView(View):
    """Get list of fee discounts linked to a master discount"""

    def get(self, request, pk):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=404)

        try:
            finance_service = FinanceService(school)
            discounts = finance_service.get_base_queryset(FeeDiscount).filter(
                master_discount_id=pk
            ).select_related('fee_category').values('id', 'name', 'fee_category__name', 'discount_mode', 'discount_value')

            items = [
                {
                    'id': str(d['id']),
                    'name': d['name'],
                    'fee_category': d['fee_category__name'],
                    'mode': d['discount_mode'],
                    'value': str(d['discount_value'])
                }
                for d in discounts
            ]
            return JsonResponse({'items': items})
        except Exception as e:
            logger.error(f"Error fetching master discount usage: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

