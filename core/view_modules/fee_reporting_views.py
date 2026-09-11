"""Phase 3 (UI) — expose new finance backend capabilities in the staff UI:
student statement, payment reversal, scholarships/waivers, year-scoped reports
+ CSV export, and fee-ledger drift visibility.

These reuse the year-aware services built in the backend remediation
(FinanceService, FeeReportingService) and the shared year-context helpers.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.http import JsonResponse, Http404, HttpResponse
from django.urls import reverse
from django.views.generic import TemplateView, View

from core.models import (
    Student, FeeCategory, AcademicYear, Guardian, StudentGuardianRelation, FinanceFee,
    FeeCollection, FeeReceiptSettings,
)
from core.services.finance_service import FinanceService
from core.services.fee_reporting_service import FeeReportingService
from core.services.defaulters_service import DefaultersService
from core.services.currency_service import CurrencyService
from core.services.exceptions import (
    ValidationException, NotFoundException, BusinessLogicException,
)
from core.view_modules.finance_year_context import (
    build_year_context, resolve_selected_year, resolve_student_fee_collections,
)

logger = logging.getLogger(__name__)


class StudentStatementView(TemplateView):
    """Printable per-student fee statement for one academic year."""
    template_name = 'core/fees/student_statement.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        selected_year = resolve_selected_year(self.request, school)
        student_id = self.request.GET.get('student_id')
        student = None
        statement = None
        fee_collections = FeeCollection.objects.none()
        selected_fee_collection_id = None
        if student_id:
            student = Student.objects.filter(id=student_id, tenant=school).first()
            if student and selected_year is not None:
                statement = FeeReportingService(school).student_statement(student, selected_year)
                fee_collections, selected_fee_collection_id = resolve_student_fee_collections(
                    self.request, school, student, selected_year,
                )

        context.update({
            'school': school,
            'student': student,
            'statement': statement,
            'fee_collections': fee_collections,
            'selected_fee_collection_id': selected_fee_collection_id,
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
            'back_url': self.request.GET.get('back', reverse('core:finance_dashboard')),
            'crumbs': [
                {'label': 'Fees', 'url': reverse('core:finance_dashboard')},
                {'label': 'Student Statement'},
            ],
        })
        context.update(build_year_context(self.request, school))
        return context


class StudentCollectionReceiptPDFView(View):
    """Printable PDF fee receipt for one student's charges in a single fee
    collection (Particulars / Summary / Payment History)."""

    def get(self, request, *args, **kwargs):
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        student_id = request.GET.get('student_id')
        fee_collection_id = request.GET.get('fee_collection')
        if not student_id or not fee_collection_id:
            return HttpResponse('student_id and fee_collection are required', status=400)

        student = Student.objects.filter(id=student_id, tenant=school).first()
        fee_collection = FeeCollection.objects.filter(id=fee_collection_id, tenant=school).first()
        if not student or not fee_collection:
            raise Http404("Student or fee collection not found")

        try:
            receipt = FeeReportingService(school).student_collection_receipt(student, fee_collection)
        except NotFoundException as e:
            raise Http404(str(e))

        html_content = render_to_string('core/fees/student_collection_receipt_pdf.html', {
            'school': school,
            'receipt': receipt,
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
            'cashier': FeeReceiptSettings.get_settings(school).cashier,
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        filename = f"fee_receipt_{student.admission_no or student.id}_{fee_collection.name}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class CollectFeePaymentReceiptPDFView(View):
    """Printable PDF receipt for one specific payment submission (identified
    by its receipt/reference number) within a student's fee collection —
    the Collect Fees page's "print this receipt" action, as opposed to
    StudentCollectionReceiptPDFView's full collection summary."""

    def get(self, request, *args, **kwargs):
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        from core.utils.number_to_words import amount_to_words

        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        student_id = request.GET.get('student_id')
        fee_collection_id = request.GET.get('fee_collection')
        receipt_no = request.GET.get('receipt_no')
        if not student_id or not fee_collection_id or not receipt_no:
            return HttpResponse('student_id, fee_collection and receipt_no are required', status=400)

        student = Student.objects.filter(id=student_id, tenant=school).first()
        if not student:
            raise Http404("Student not found")

        reporting = FeeReportingService(school)

        # The collection is resolved from the payment itself — the page's
        # collection dropdown (which feeds this link) can be on a different
        # term than the payment being printed. Fall back to the query param.
        fee_collection = (
            reporting.collection_for_payment(student, receipt_no)
            or FeeCollection.objects.filter(id=fee_collection_id, tenant=school).first()
        )
        if not fee_collection:
            raise Http404("Fee collection not found")

        # The payment itself is resolved directly from its reference number
        # (authoritative, and independent of how the collection's particulars
        # were snapshotted / later edited), not by scanning the collection
        # receipt's payment_history — that scan misses payments whose ledger
        # rows don't line up with the collection's current particular ids.
        by_ref = reporting.receipt_by_reference(receipt_no, student_ids=[student.id])
        if by_ref is None:
            raise Http404("No payment with this receipt number was found for this student")
        payment = {
            'receipt_no': receipt_no,
            'date': by_ref['date'],
            'mode': by_ref['mode'],
            'notes': by_ref['notes'],
            'cashier': by_ref['cashier'],
            'amount': by_ref['amount'],
            'lines': by_ref['lines'],
        }

        # Surrounding fee summary (particulars / totals). If this student has no
        # charge under this exact collection, fall back to a minimal summary
        # built from the payment rows so the receipt still renders.
        try:
            receipt = reporting.student_collection_receipt(student, fee_collection)
        except NotFoundException:
            receipt = {
                'student_name': by_ref['student_name'],
                'admission_no': by_ref['admission_no'],
                'class_name': '',
                'batch_name': '',
                'fee_collection_name': fee_collection.name,
                'invoice_number': None,
                'particulars': by_ref['lines'],
                'total_particular_fees': by_ref['amount'],
                'total_discount': 0,
                'total_fine': 0,
                'total_fees': by_ref['amount'],
                'payment_done': by_ref['amount'],
                'amount_to_pay': 0,
                'payment_history': [payment],
            }

        html_content = render_to_string('core/fees/collection_payment_receipt_pdf.html', {
            'school': school,
            'receipt': receipt,
            'payment': payment,
            'guardian': reporting.resolve_guardian_display(student),
            'amount_in_words': amount_to_words(payment['amount']),
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
            # NOTE: the cashier is intentionally NOT passed to the receipt — it
            # belongs only on the on-screen ledger / payment history.
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="receipt_{receipt_no}.pdf"'
        return response


class DefaultersReportView(TemplateView):
    """On-screen "Fees Defaulters" list.

    A student is a defaulter when a fee collection's ``due_date`` has passed and
    they still owe against it (any outstanding balance). Tick "include not-yet-due
    collections" (``?include_upcoming=1``) to generate the list before a due date.

    The list is computed live on every page load — nothing is stored — so it
    always reflects today's date against each collection's due date.
    """
    template_name = 'core/fees/defaulters_report.html'

    def _resolve(self, request):
        """(school, selected_year, batch, include_upcoming) from the request."""
        from core.models import Batch

        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        selected_year = resolve_selected_year(request, school)
        include_upcoming = request.GET.get('include_upcoming') in ('1', 'true', 'on')
        batch_id = request.GET.get('batch_id')
        batch = None
        if batch_id and batch_id != 'all':
            batch = Batch.objects.filter(id=batch_id, tenant=school).first()
        return school, selected_year, batch, include_upcoming

    def get(self, request, *args, **kwargs):
        if request.GET.get('export'):
            return self._export_csv(request)
        return super().get(request, *args, **kwargs)

    def _export_csv(self, request):
        import csv

        school, selected_year, batch, include_upcoming = self._resolve(request)
        if selected_year is None:
            return HttpResponse('No academic year configured', status=400)

        report = DefaultersService(school).list_defaulters(
            academic_year=selected_year, batch=batch, include_upcoming=include_upcoming,
        )
        student_rows = report['student_rows']
        if request.GET.get('export') == 'selected':
            wanted = set(request.GET.getlist('student_ids'))
            student_rows = [r for r in student_rows if str(r.student.id) in wanted]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="fee_defaulters.csv"'
        writer = csv.writer(response)
        writer.writerow(['Admission No', 'Student', 'Batch', 'Oldest due date',
                         'Days overdue', 'Outstanding'])
        for r in student_rows:
            writer.writerow([
                r.admission_no, r.student_name, r.batch_name,
                r.oldest_due_date.isoformat() if r.oldest_due_date else '',
                r.max_days_overdue, f"{r.outstanding:.2f}",
            ])
        return response

    def get_context_data(self, **kwargs):
        from core.models import Batch

        context = super().get_context_data(**kwargs)
        school, selected_year, batch, include_upcoming = self._resolve(self.request)

        report = None
        if selected_year is not None:
            report = DefaultersService(school).list_defaulters(
                academic_year=selected_year, batch=batch,
                include_upcoming=include_upcoming,
            )

        batches = Batch.objects.filter(
            tenant=school, is_deleted=False, is_active=True,
        ).order_by('name')
        if selected_year is not None:
            batches = batches.filter(academic_year=selected_year)

        group_by = self.request.GET.get('group_by', 'student')
        if group_by not in ('student', 'batch'):
            group_by = 'student'

        context.update({
            'school': school,
            'report': report,
            'available_batches': batches,
            'selected_batch': batch,
            'group_by': group_by,
            'include_upcoming': include_upcoming,
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
            'back_url': self.request.GET.get('back', reverse('core:fee_reports')),
            'crumbs': [
                {'label': 'Fees', 'url': reverse('core:finance_dashboard')},
                {'label': 'Reports', 'url': reverse('core:fee_reports')},
                {'label': 'Defaulters'},
            ],
        })
        context.update(build_year_context(self.request, school))
        return context


class DefaultersReportPDFView(View):
    """Printable "Fees Defaulters" list.

    Two modes:
      * ``student_ids`` given (repeated) — print exactly those students, in the
        given order. Used by the Batch Fee Report screen's bulk "Print PDF".
      * no ``student_ids`` — print the live due-date-driven defaulters list from
        :class:`DefaultersService` (same as the on-screen report).

    GET params: ``student_ids`` (repeated, optional), ``batch_id`` (optional),
    ``academic_year`` (optional), ``include_upcoming`` (optional, live mode).

    One row per student: name, batch, all overdue fee collections (terms)
    stacked in one cell, and the student's total outstanding amount.
    """

    def get(self, request, *args, **kwargs):
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        from core.models import Batch

        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        selected_year = resolve_selected_year(request, school)

        batch_id = request.GET.get('batch_id')
        header_batch = None
        if batch_id and batch_id != 'all':
            header_batch = Batch.objects.filter(id=batch_id, tenant=school).first()

        student_ids = request.GET.getlist('student_ids')
        if student_ids:
            rows, total = self._rows_from_selection(
                school, selected_year, header_batch, student_ids,
            )
        else:
            include_upcoming = request.GET.get('include_upcoming') in ('1', 'true', 'on')
            report = DefaultersService(school).list_defaulters(
                academic_year=selected_year, batch=header_batch,
                include_upcoming=include_upcoming,
            )
            rows = [{
                'name': s.student_name,
                'batch': s.batch_name,
                'collections': [ln.collection_name for ln in s.lines],
                'amount': s.outstanding,
            } for s in report['student_rows']]
            total = report['total']

        html_content = render_to_string('core/fees/defaulters_report_pdf.html', {
            'school': school,
            'rows': rows,
            'total': total,
            'class_label': header_batch.name if header_batch else 'All Batches',
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="fee_defaulters.pdf"'
        return response

    def _rows_from_selection(self, school, selected_year, header_batch, student_ids):
        """Build PDF rows for a hand-picked set of students (bulk action)."""
        from core.models import BatchStudent, FinanceFee

        # Preserve the caller's ordering of students.
        students = list(Student.objects.filter(id__in=student_ids, tenant=school))
        students.sort(key=lambda s: student_ids.index(str(s.id)))

        # Resolve each student's current batch once (for the "Current batch" column).
        bs_qs = BatchStudent.objects.filter(
            tenant=school, student__in=students, is_active=True
        ).select_related('batch')
        if selected_year is not None:
            bs_qs = bs_qs.filter(batch__academic_year=selected_year)
        current_batch_by_student = {bs.student_id: bs.batch for bs in bs_qs}

        fee_filter = {'tenant': school, 'student__in': students, 'balance__gt': 0}
        if selected_year is not None:
            fee_filter['academic_year'] = selected_year
        fees_by_student = {}
        for fee in FinanceFee.objects.filter(**fee_filter).select_related(
            'fee_collection', 'fee_category', 'batch'
        ).order_by('transaction_date'):
            fees_by_student.setdefault(fee.student_id, []).append(fee)

        rows = []
        for student in students:
            name = f"{student.first_name} {student.last_name}".strip()
            current_batch = current_batch_by_student.get(student.id)
            batch_label = current_batch.name if current_batch else (
                header_batch.name if header_batch else '—'
            )
            student_fees = fees_by_student.get(student.id, [])
            collections = []
            amount = Decimal('0.00')
            for fee in student_fees:
                if fee.fee_collection:
                    collections.append(fee.fee_collection.name)
                elif fee.fee_category:
                    collections.append(fee.fee_category.name)
                amount += fee.balance
            rows.append({
                'name': name,
                'batch': batch_label,
                'collections': collections or ['—'],
                'amount': amount,
            })

        total = sum((r['amount'] for r in rows), Decimal('0.00'))
        return rows, total


class PaymentReversalView(View):
    """Reverse a recorded fee payment (compensating entry; preserves history)."""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        fee_transaction_id = request.POST.get('fee_transaction_id')
        reason = request.POST.get('reason', '').strip()
        if not fee_transaction_id:
            return JsonResponse({'error': 'Payment reference is required'}, status=400)

        try:
            refund = FinanceService(school).reverse_payment(
                fee_transaction_id, reason=reason, user=getattr(request, 'user', None),
            )
            return JsonResponse({
                'success': True,
                'message': 'Payment reversed successfully',
                'refund_id': str(refund.id),
            })
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except (BusinessLogicException, ValidationException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error("Error reversing payment: %s", e)
            return JsonResponse({'error': str(e)}, status=500)


class GrantWaiverView(View):
    """Grant a scholarship/waiver against a student's charge for a year."""

    def post(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        student_id = request.POST.get('student_id')
        fee_category_id = request.POST.get('fee_category_id')
        waiver_type = request.POST.get('waiver_type', 'SCHOLARSHIP')
        academic_year_id = request.POST.get('academic_year')
        amount = request.POST.get('amount')
        percentage = request.POST.get('percentage')
        reason = request.POST.get('reason', '').strip()

        if not all([student_id, fee_category_id]):
            return JsonResponse({'error': 'Student and fee category are required'}, status=400)

        student = Student.objects.filter(id=student_id, tenant=school).first()
        fee_category = FeeCategory.objects.filter(id=fee_category_id, tenant=school).first()
        if not student or not fee_category:
            return JsonResponse({'error': 'Student or fee category not found'}, status=404)

        academic_year = None
        if academic_year_id:
            academic_year = AcademicYear.objects.filter(id=academic_year_id, tenant=school).first()

        try:
            amount_val = Decimal(amount) if amount else None
            percentage_val = Decimal(percentage) if percentage else None
        except (InvalidOperation, TypeError):
            return JsonResponse({'error': 'Invalid amount or percentage'}, status=400)

        try:
            waiver, fee, waiver_amount = FinanceService(school).grant_waiver(
                student, fee_category, waiver_type,
                academic_year=academic_year, amount=amount_val,
                percentage=percentage_val, reason=reason,
            )
            return JsonResponse({
                'success': True,
                'message': f'{waiver_type} of {waiver_amount} granted',
                'waiver_id': str(waiver.id),
                'remaining_balance': float(fee.balance),
            })
        except (BusinessLogicException, ValidationException) as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error("Error granting waiver: %s", e)
            return JsonResponse({'error': str(e)}, status=500)


class FeeYearReportsView(TemplateView):
    """Year-scoped finance reports hub: outstanding balances, payment summary,
    academic-year summary, and class/grade breakdown. Supports CSV export."""
    template_name = 'core/fees/year_reports.html'

    def get(self, request, *args, **kwargs):
        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        selected_year = resolve_selected_year(request, school)
        export = request.GET.get('export')

        if export and selected_year is not None:
            reporting = FeeReportingService(school)
            if export == 'outstanding':
                rows = reporting.outstanding_balance_report(selected_year)
                csv_text = reporting.to_csv(rows, ['admission_no', 'student_name', 'outstanding'])
                filename = f"outstanding_{selected_year.name}.csv"
            elif export == 'class':
                rows = reporting.class_based_report(selected_year)
                csv_text = reporting.to_csv(rows, ['grade', 'batch', 'students', 'collected', 'outstanding'])
                filename = f"class_report_{selected_year.name}.csv"
            else:
                csv_text, filename = "", "report.csv"
            response = HttpResponse(csv_text, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from core.models import Batch

        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        selected_year = resolve_selected_year(self.request, school)

        # Get batch filter from query params (for per-class filtering)
        batch_id = self.request.GET.get('batch')
        batch = None
        if batch_id and selected_year:
            try:
                batch = Batch.objects.filter(
                    tenant=school, id=batch_id, academic_year=selected_year
                ).first()
            except (ValueError, ValidationError):
                # Invalid batch_id format (not a valid UUID) — silently ignore
                pass

        reporting = FeeReportingService(school)
        if selected_year is not None:
            # Pass batch parameter to filter outstanding_balance_report by class
            context.update({
                'outstanding_rows': reporting.outstanding_balance_report(selected_year, batch=batch),
                'payment_summary': reporting.payment_summary(selected_year),
                'year_summary': reporting.academic_year_summary(selected_year),
                'class_rows': reporting.class_based_report(selected_year),
            })

            # Provide list of batches for the filter dropdown
            batches = Batch.objects.filter(
                tenant=school, academic_year=selected_year, is_deleted=False
            ).order_by('name')
            context['available_batches'] = batches
            context['selected_batch'] = batch

        context['school'] = school
        context['currency_symbol'] = CurrencyService(school).get_currency_symbol()
        context.update({
            'back_url': self.request.GET.get('back', reverse('core:finance_dashboard')),
            'crumbs': [
                {'label': 'Fees', 'url': reverse('core:finance_dashboard')},
                {'label': 'Year Reports'},
            ],
        })
        context.update(build_year_context(self.request, school))
        return context


class FeeStatisticsReportView(TemplateView):
    """Fedena-style Fee Statistics: monthly collection trend + category
    breakdown for one academic year, for charting."""
    template_name = 'core/fees/statistics_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")
        selected_year = resolve_selected_year(self.request, school)

        statistics = None
        if selected_year is not None:
            statistics = FeeReportingService(school).fee_statistics(selected_year)

        context.update({
            'school': school,
            'statistics': statistics,
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
            'back_url': self.request.GET.get('back', reverse('core:finance_dashboard')),
            'crumbs': [
                {'label': 'Fees', 'url': reverse('core:finance_dashboard')},
                {'label': 'Statistics Report'},
            ],
        })
        context.update(build_year_context(self.request, school))
        return context


class FinanceTrackView(TemplateView):
    """Step 4 hub: student ledger + family accounts."""
    template_name = 'core/finance/track.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.urls import reverse
        context['back_url'] = self.request.GET.get('back', reverse('core:finance_dashboard'))
        context['crumbs'] = [
            {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
            {'label': 'Track & Monitor'},
        ]
        return context


class FamilyAccountView(TemplateView):
    """Guardian-centric view: one row per child with due/paid/balance."""
    template_name = 'core/finance/family_accounts.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        school = self.request.tenant
        q = (self.request.GET.get('q') or '').strip()
        guardian_id = self.request.GET.get('guardian')
        year = AcademicYear.objects.filter(tenant=school, is_active=True).first()

        guardians = Guardian.objects.filter(tenant=school, is_active=True)
        if q:
            guardians = guardians.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q)
                | Q(mobile_phone__icontains=q) | Q(email__icontains=q)
            )
        ctx['guardians'] = guardians.order_by('last_name', 'first_name')[:25] if q else []
        ctx['q'] = q

        guardian = None
        if guardian_id:
            try:
                guardian = Guardian.objects.filter(
                    tenant=school, id=guardian_id).first()
            except (ValidationError, ValueError):
                guardian = None
        ctx['guardian'] = guardian
        if guardian:
            relations = StudentGuardianRelation.objects.filter(
                tenant=school, guardian=guardian
            ).select_related('student')
            children = []
            family_total = family_paid = family_balance = Decimal('0.00')
            for rel in relations:
                agg = FinanceFee.objects.filter(
                    tenant=school, student=rel.student,
                    **({'academic_year': year} if year else {}),
                ).aggregate(total=Sum('particular_total'), balance=Sum('balance'))
                total = agg['total'] or Decimal('0.00')
                balance = agg['balance'] or Decimal('0.00')
                paid = max(total - balance, Decimal('0.00'))
                children.append({'student': rel.student, 'relation': rel.relation,
                                 'total': total, 'paid': paid, 'balance': balance})
                family_total += total; family_paid += paid; family_balance += balance
            ctx.update(children=children, family_total=family_total,
                       family_paid=family_paid, family_balance=family_balance,
                       selected_year=year)
        from django.urls import reverse
        ctx['back_url'] = self.request.GET.get('back', reverse('core:finance_track'))
        ctx['crumbs'] = [
            {'label': 'Finance', 'url': reverse('core:finance_dashboard')},
            {'label': 'Track & Monitor', 'url': reverse('core:finance_track')},
            {'label': 'Family Accounts'},
        ]
        return ctx


class StatementDistributionView(TemplateView):
    """Modal data for statement distribution UI.

    Returns JSON with available guardians and distribution options.
    """
    template_name = None

    def get(self, request, *args, **kwargs):
        from core.services.fee_statement_service import FeeStatementService
        import json

        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        student_id = request.GET.get('student_id')
        if not student_id:
            return JsonResponse({'error': 'Student ID is required'}, status=400)

        try:
            student = Student.objects.get(id=student_id, tenant=school)
        except Student.DoesNotExist:
            return JsonResponse({'error': 'Student not found'}, status=404)

        # Get guardians
        service = FeeStatementService(school)
        guardians = service.get_student_guardians(student)

        guardian_data = [
            {
                'id': str(g.id),
                'name': f"{g.first_name} {g.last_name}",
                'phone': g.mobile_phone or '',
                'email': g.email or '',
                'has_phone': bool(g.mobile_phone),
                'has_email': bool(g.email),
            }
            for g in guardians
        ]

        return JsonResponse({
            'student_id': str(student.id),
            'student_name': f"{student.first_name} {student.last_name}",
            'guardians': guardian_data,
            'channels': [
                {'value': 'sms', 'label': 'SMS', 'icon': 'fas fa-mobile-alt'},
                {'value': 'email', 'label': 'Email', 'icon': 'fas fa-envelope'},
                {'value': 'portal', 'label': 'Parent Portal', 'icon': 'fas fa-share'},
            ],
        })


class StatementDistributeSendView(View):
    """Handle actual statement distribution via selected channels."""

    def post(self, request, *args, **kwargs):
        from core.services.fee_statement_service import FeeStatementService
        import json

        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        student_id = data.get('student_id')
        academic_year_id = data.get('academic_year_id')
        guardian_ids = data.get('guardian_ids', [])
        channels = data.get('channels', [])
        custom_message = data.get('custom_message', '').strip()

        if not all([student_id, academic_year_id]):
            return JsonResponse({'error': 'Student and academic year are required'}, status=400)

        try:
            student = Student.objects.get(id=student_id, tenant=school)
            academic_year = AcademicYear.objects.get(id=academic_year_id, tenant=school)
        except (Student.DoesNotExist, AcademicYear.DoesNotExist):
            return JsonResponse({'error': 'Student or academic year not found'}, status=404)

        try:
            service = FeeStatementService(school)
            result = service.distribute_statement(
                student=student,
                academic_year=academic_year,
                guardian_ids=guardian_ids,
                channels=channels,
                custom_message=custom_message if custom_message else None,
            )

            return JsonResponse({
                'success': result['success'],
                'total': result['total'],
                'results': result['results'],
                'errors': result['errors'],
                'message': (
                    f"Statement distributed successfully to {result['total']} recipient(s)"
                    if result['success']
                    else f"Distribution completed with {len(result['errors'])} error(s)"
                ),
            })
        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except Exception as e:
            logger.error(f"Error distributing statement: {e}", exc_info=True)
            return JsonResponse({'error': f'Distribution failed: {str(e)}'}, status=500)


class PaymentAgreementCreateView(TemplateView):
    """
    Create a new payment agreement for a student.
    GET: Renders form pre-filled with student's outstanding balance and guardians.
    POST: Creates the agreement and installments.
    """
    template_name = 'core/fees/payment_agreement_form.html'

    def get_context_data(self, **kwargs):
        from core.models import PaymentAgreement, StudentGuardianRelation
        from core.services.payment_agreement_service import PaymentAgreementService
        from core.services.fee_statement_service import FeeStatementService
        from datetime import date, timedelta

        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        student_id = self.request.GET.get('student_id')
        student = None
        guardians = []
        guardians_with_data = []
        primary_guardian = None
        outstanding_balance = Decimal('0.00')
        term_breakdown = {'rows': [], 'total': Decimal('0.00')}

        if student_id:
            student = Student.objects.filter(id=student_id, tenant=school).first()
            if student:
                # Get student's guardians
                fee_service = FeeStatementService(school)
                guardians = fee_service.get_student_guardians(student)

                # Build guardian data for form auto-fill (data attributes on select options)
                for guardian in guardians:
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

                    # Check if this guardian is the immediate/primary contact
                    is_primary = StudentGuardianRelation.objects.filter(
                        student=student,
                        guardian=guardian,
                        is_immediate_contact=True,
                        tenant=school,
                    ).exists()

                    if is_primary:
                        primary_guardian = guardian

                    guardians_with_data.append({
                        'id': str(guardian.id),
                        'name': f"{guardian.first_name} {guardian.last_name}".strip(),
                        'address': address_str,
                        'phone': phone,
                        'is_primary': is_primary,
                    })

                # Get outstanding balance
                outstanding_qs = FinanceFee.objects.filter(
                    tenant=school,
                    student=student,
                    balance__gt=0,
                )
                outstanding_balance = outstanding_qs.aggregate(
                    total=Sum('balance')
                )['total'] or Decimal('0.00')

                # Per-term breakdown of the outstanding balance (collections are
                # termly), so the debtor can see how the total is built up.
                term_breakdown = PaymentAgreementService(school).outstanding_by_term(student)

        # Fetch director name from default school signature
        director_display_name = ''
        from core.models import SchoolSignature
        head_signature = SchoolSignature.objects.filter(tenant=school, is_default=True).first()
        if head_signature and head_signature.name:
            director_display_name = head_signature.name

        context.update({
            'school': school,
            'student': student,
            'guardians': guardians,
            'guardians_with_data': guardians_with_data,
            'primary_guardian': primary_guardian,
            'outstanding_balance': outstanding_balance,
            'term_breakdown': term_breakdown,
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
            'director_display_name': director_display_name,
            'operations_manager_name': school.operations_manager_name or '',
            'back_url': self.request.GET.get('back', reverse('core:fee_batch_report')),
            'crumbs': [
                {'label': 'Fees', 'url': reverse('core:finance_dashboard')},
                {'label': 'Defaulters', 'url': reverse('core:fee_batch_report')},
                {'label': 'Create Agreement'},
            ],
        })
        context.update(build_year_context(self.request, school))
        return context

    def post(self, request, *args, **kwargs):
        from core.services.payment_agreement_service import PaymentAgreementService
        import json
        from datetime import datetime

        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        # Parse and validate request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            return JsonResponse({'error': f'Invalid JSON: {str(e)}'}, status=400)

        try:
            student_id = data.get('student_id')
            debtor_name = data.get('debtor_name')
            unpaid_fees_amount = Decimal(str(data.get('unpaid_fees_amount', 0)))
            other_amount = Decimal(str(data.get('other_amount', 0)))
            other_description = data.get('other_description')
            interest_rate = Decimal(str(data.get('interest_rate', 5)))
            guardian_id = data.get('guardian_id')
            nrc_number = data.get('nrc_number')
            debtor_address = data.get('debtor_address')
            installments = data.get('installments', [])

            # Parse dates with explicit error handling
            try:
                start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
                end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
            except (ValueError, TypeError) as e:
                return JsonResponse({'error': f'Invalid date format. Use YYYY-MM-DD: {str(e)}'}, status=400)

            # Validate installments data
            parsed_installments = []
            try:
                for i, inst in enumerate(installments):
                    try:
                        due_date = datetime.strptime(inst.get('due_date'), '%Y-%m-%d').date()
                    except (ValueError, TypeError) as e:
                        return JsonResponse({'error': f'Invalid date in installment {i+1}. Use YYYY-MM-DD: {str(e)}'}, status=400)

                    try:
                        amount = Decimal(str(inst.get('amount')))
                    except (ValueError, TypeError, InvalidOperation) as e:
                        return JsonResponse({'error': f'Invalid amount in installment {i+1}: {str(e)}'}, status=400)

                    parsed_installments.append({
                        'due_date': due_date,
                        'amount': amount,
                    })
            except (KeyError, TypeError) as e:
                return JsonResponse({'error': f'Invalid installment data: {str(e)}'}, status=400)

            service = PaymentAgreementService(school)
            agreement = service.create_agreement(
                student_id=student_id,
                debtor_name=debtor_name,
                unpaid_fees_amount=unpaid_fees_amount,
                installments=parsed_installments,
                start_date=start_date,
                end_date=end_date,
                guardian_id=guardian_id,
                nrc_number=nrc_number,
                debtor_address=debtor_address,
                other_amount=other_amount,
                other_description=other_description,
                interest_rate=interest_rate,
                created_by=request.user if request.user.is_authenticated else None,
            )

            return JsonResponse({
                'success': True,
                'agreement_id': str(agreement.id),
                'message': f'Payment agreement created successfully',
            })

        except ValidationException as e:
            return JsonResponse({'error': str(e)}, status=400)
        except NotFoundException as e:
            return JsonResponse({'error': str(e)}, status=404)
        except Exception as e:
            logger.error(f"Error creating agreement: {e}", exc_info=True)
            return JsonResponse({'error': f'Failed to create agreement: {str(e)}'}, status=500)


class PaymentAgreementDetailView(TemplateView):
    """Show details of a payment agreement with schedule and payment record."""
    template_name = 'core/fees/payment_agreement_detail.html'

    def get_context_data(self, **kwargs):
        from core.services.payment_agreement_service import PaymentAgreementService
        from core.models import PaymentAgreement

        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        # Get agreement_id from URL path parameter (kwargs['pk'])
        agreement_id = kwargs.get('pk')
        agreement = None

        if agreement_id:
            try:
                service = PaymentAgreementService(school)
                agreement_context = service.get_agreement_context(agreement_id)
                context.update(agreement_context)
            except NotFoundException:
                context['error'] = "Agreement not found"

        # Set default agreement to None if not already set by service context
        context.setdefault('agreement', None)
        context.update({
            'school': school,
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
            'back_url': self.request.GET.get('back', reverse('core:payment_agreement_list')),
            'crumbs': [
                {'label': 'Fees', 'url': reverse('core:finance_dashboard')},
                {'label': 'Payment Agreements', 'url': reverse('core:payment_agreement_list')},
                {'label': 'Details'},
            ],
        })
        context.update(build_year_context(self.request, school))
        return context


class PaymentAgreementPDFView(View):
    """Generate PDF for a payment agreement."""

    def get(self, request, *args, **kwargs):
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        from core.services.payment_agreement_service import PaymentAgreementService

        school = getattr(request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        # Get agreement_id from URL path parameter (kwargs['pk'])
        agreement_id = kwargs.get('pk')
        if not agreement_id:
            raise Http404("Agreement ID is required")

        try:
            service = PaymentAgreementService(school)
            context = service.get_agreement_context(agreement_id)
        except NotFoundException:
            raise Http404("Agreement not found")

        context.update({
            'school': school,
        })

        html_content = render_to_string('core/fees/payment_agreement_pdf.html', context)
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        filename = f"payment_agreement_{context['agreement'].student.admission_no}_{str(agreement_id)[:8]}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class PaymentAgreementListView(TemplateView):
    """List all payment agreements for the school, filterable by status."""
    template_name = 'core/fees/payment_agreement_list.html'

    def get_context_data(self, **kwargs):
        from core.models import PaymentAgreement

        context = super().get_context_data(**kwargs)
        school = getattr(self.request, 'tenant', None)
        if not school:
            raise Http404("School not found")

        status_filter = self.request.GET.get('status', '')

        agreements = PaymentAgreement.objects.filter(tenant=school).select_related(
            'student', 'guardian', 'created_by'
        ).order_by('-created_at')

        if status_filter:
            agreements = agreements.filter(status=status_filter)

        context.update({
            'school': school,
            'agreements': agreements,
            'status_filter': status_filter,
            'status_choices': PaymentAgreement.STATUS_CHOICES,
            'currency_symbol': CurrencyService(school).get_currency_symbol(),
            'back_url': self.request.GET.get('back', reverse('core:finance_dashboard')),
            'crumbs': [
                {'label': 'Fees', 'url': reverse('core:finance_dashboard')},
                {'label': 'Payment Agreements'},
            ],
        })
        context.update(build_year_context(self.request, school))
        return context


class PaymentAgreementBulkCreateView(View):
    """Bulk create payment agreements for multiple students with shared terms."""

    def post(self, request, *args, **kwargs):
        import json
        from datetime import datetime
        from core.services.payment_agreement_service import PaymentAgreementService

        school = getattr(request, 'tenant', None)
        if not school:
            return JsonResponse({'error': 'School not found'}, status=400)

        # Parse and validate request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            return JsonResponse({'error': f'Invalid JSON: {str(e)}'}, status=400)

        try:
            student_ids = data.get('student_ids', [])
            if not student_ids:
                return JsonResponse({'error': 'No students selected'}, status=400)

            # Parse dates with explicit error handling
            try:
                start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d').date()
                end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d').date()
            except (ValueError, TypeError) as e:
                return JsonResponse({'error': f'Invalid date format. Use YYYY-MM-DD: {str(e)}'}, status=400)

            if start_date >= end_date:
                return JsonResponse({'error': 'End date must be after start date'}, status=400)

            try:
                interest_rate = Decimal(str(data.get('interest_rate', 5)))
            except (ValueError, TypeError, InvalidOperation) as e:
                return JsonResponse({'error': f'Invalid interest rate: {str(e)}'}, status=400)

            installment_count = data.get('installment_count', 3)
            if not isinstance(installment_count, int) or installment_count < 1 or installment_count > 24:
                return JsonResponse({'error': 'Installment count must be between 1 and 24'}, status=400)

            service = PaymentAgreementService(school)
            results = service.bulk_create_agreements(
                student_ids=student_ids,
                start_date=start_date,
                end_date=end_date,
                interest_rate=interest_rate,
                installment_count=installment_count,
                created_by=request.user if request.user.is_authenticated else None,
            )

            return JsonResponse({'results': results})

        except Exception as e:
            logger.error(f"Error in bulk agreement creation: {e}", exc_info=True)
            return JsonResponse({'error': f'Failed to create agreements: {str(e)}'}, status=500)
