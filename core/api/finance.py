"""
Finance domain API — Invoicing, fees, transactions.

Covers:
- Invoice management (create, list, update, mark paid)
- Fee categories (fixed charge types)
- Finance transactions (cash in/out)
- Fee discounts and fine slabs (deductions and penalties)
- Student fee balances

Reuses existing services: FinanceService, FeeService (in core/services/finance_service.py, etc.)
"""

from datetime import date, datetime, timedelta

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter

from core.models import (
    FamilyInvoice, FeeCategory, FinanceTransaction,
    Student
)
from core.authz.drf import ModuleEnabled, HasPermission
from core.services.fee_reporting_service import FeeReportingService
from core.view_modules.finance_year_context import resolve_selected_year
from core.serializers.finance_serializers import (
    FeeCategorySerializer, FeeDiscountSerializer, FineSlabSerializer,
    FinanceTransactionCategorySerializer, FinanceTransactionSerializer,
    StudentFeeSerializer, InvoiceLineSerializer, InvoiceSerializer
)
from core.api.base import TenantAwareViewSet, TenantAwareReadOnlyViewSet


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class FeeCategoryViewSet(TenantAwareViewSet):
    """
    Fee category management — define what fees are charged.

    Covers:
    - List/create/update/delete fee categories
    - Filter by active status
    """
    queryset = FeeCategory.objects.all()
    serializer_class = FeeCategorySerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.fees.view", write="finance.fees.manage"),
    ]
    module = "finance"
    filterset_fields = ['academic_year']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class FeeDiscountViewSet(TenantAwareViewSet):
    """
    Fee discount management — define discounts (scholarships, waivers, etc.).

    Covers:
    - List/create/update/delete discounts
    - Filter by category or discount type
    """
    queryset = FeeDiscount.objects.all()
    serializer_class = FeeDiscountSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.discounts.view", write="finance.discounts.manage"),
    ]
    module = "finance"
    filterset_fields = ['fee_category', 'discount_type', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        return super().get_queryset().select_related('fee_category')


class FineSlabViewSet(TenantAwareViewSet):
    """
    Fine slab management — define late payment penalties.

    Covers:
    - List/create/update/delete fine slabs
    - Filter by fine type or applicability
    """
    queryset = FineSlab.objects.all()
    serializer_class = FineSlabSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.fines.view", write="finance.fines.manage"),
    ]
    module = "finance"
    filterset_fields = ['fine_mode', 'is_active']
    search_fields = ['fine_name']
    ordering_fields = ['fine_name', 'days_after_due']
    ordering = ['days_after_due']


class FinanceTransactionCategoryViewSet(TenantAwareViewSet):
    """
    Finance transaction category management — define transaction types.

    Covers:
    - List/create/update/delete transaction categories
    - Filter by category type (income, expense, etc.)
    """
    queryset = FinanceTransactionCategory.objects.all()
    serializer_class = FinanceTransactionCategorySerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.transactions.view", write="finance.transactions.manage"),
    ]
    module = "finance"
    filterset_fields = ['is_income']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class FinanceTransactionViewSet(TenantAwareViewSet):
    """
    Finance transaction management — record cash in/out.

    Covers:
    - List/create/update/delete transactions
    - Filter by date, category, type
    - Search by description or reference number
    """
    queryset = FinanceTransaction.objects.all()
    serializer_class = FinanceTransactionSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.transactions.view", write="finance.transactions.manage"),
    ]
    module = "finance"
    filterset_fields = ['category', 'payment_method', 'student', 'employee', 'transaction_date']
    search_fields = ['title', 'description', 'reference_number']
    ordering_fields = ['transaction_date', 'amount', 'created_at']
    ordering = ['-transaction_date']

    def get_queryset(self):
        return super().get_queryset().select_related('category', 'student', 'employee')

    @extend_schema(
        description="List all finance transactions (paginated, filterable by category/payment method/date)",
        parameters=[
            OpenApiParameter(name='category', description='Filter by transaction category'),
            OpenApiParameter(name='payment_method', enum=['cash', 'card', 'bank_transfer', 'mobile_money', 'cheque', 'online', 'other']),
            OpenApiParameter(name='date_from', description='Filter transactions on or after date (YYYY-MM-DD)'),
            OpenApiParameter(name='date_to', description='Filter transactions on or before date (YYYY-MM-DD)'),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class StudentFeeViewSet(TenantAwareViewSet):
    """
    Student fee management — assign fees to students.

    Covers:
    - List/create/update/delete student fees
    - Filter by student, category, active status
    - View fee balances per student
    """
    queryset = FinanceFee.objects.all()
    serializer_class = StudentFeeSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.student-fees.view", write="finance.student-fees.manage"),
    ]
    module = "finance"
    filterset_fields = ['student', 'fee_category', 'is_paid']
    search_fields = ['student__first_name', 'student__last_name', 'invoice_number']
    ordering_fields = ['student', 'transaction_date', 'balance']
    ordering = ['transaction_date']

    def get_queryset(self):
        return super().get_queryset().select_related('student', 'fee_category')

    @extend_schema(
        description="List all student fee assignments (paginated, filterable)",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    @extend_schema(
        description="Get fee balance summary for a student",
        parameters=[
            OpenApiParameter(name='student', required=True, description='Student ID'),
        ],
    )
    def balance(self, request):
        """Get total fees due for a student."""
        student_id = request.query_params.get('student')
        if not student_id:
            return Response({'error': 'student ID required'}, status=400)

        try:
            student = Student.objects.get(id=student_id, tenant=request.tenant)
        except Student.DoesNotExist:
            return Response({'error': 'Student not found'}, status=404)

        # Compute balance from FinanceFee (unpaid charges)
        fees = FinanceFee.objects.filter(student=student, is_paid=False, tenant=request.tenant)
        total_due = sum(f.balance for f in fees)

        return Response({
            'student_id': str(student.id),
            'student_name': student.full_name,
            'total_fees': str(total_due),
            'fee_count': fees.count(),
        })


class InvoiceViewSet(TenantAwareReadOnlyViewSet):
    """
    Invoice viewing — guardian-level consolidated billing invoices.

    Covers:
    - List/retrieve invoices (read-only)
    - Filter by guardian, status
    - Download invoice PDF

    FamilyInvoice is entirely system-generated: ``InvoiceService`` upserts a
    guardian's invoice (and its per-child lines) whenever a fee charge
    exists, and recomputes subtotal/amount_paid/balance_due/status/due_date
    from those lines after every upsert and payment (see
    core/services/invoice_service.py). There is no legitimate manual
    create/update/delete or "mark paid" action — status and totals are
    always derived, never hand-set.
    """
    queryset = FamilyInvoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.invoices.view", write="finance.invoices.view"),
    ]
    module = "finance"
    filterset_fields = ['guardian', 'status']
    search_fields = ['invoice_number', 'guardian__first_name', 'guardian__last_name']
    ordering_fields = ['due_date', 'generated_at', 'status']
    ordering = ['-generated_at']

    def get_queryset(self):
        return (
            super().get_queryset()
            .select_related('guardian', 'academic_year')
            .prefetch_related('lines__student')
        )

    @extend_schema(
        description="List all invoices (paginated, filterable by guardian/status)",
        parameters=[
            OpenApiParameter(name='status', enum=['open', 'paid', 'void']),
            OpenApiParameter(name='guardian', description='Filter by guardian ID'),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['get'])
    @extend_schema(
        description="Download the invoice as a PDF (same layout as the staff/portal views)",
        responses={'application/pdf': None},
    )
    def pdf(self, request, pk=None):
        """Render the invoice PDF using the shared context builder/template
        also used by the legacy staff view (``InvoicePDFView``) and the
        parent-portal view, so all three stay visually identical."""
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        from core.services.invoice_service import build_invoice_pdf_context

        invoice = self.get_object()
        html_content = render_to_string('core/finance/invoice_pdf.html', build_invoice_pdf_context(invoice))
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="invoice_{invoice.invoice_number}.pdf"'
        return response


# ───────────────────────────────────────────────────────────────────────────
# Reports (read-only, not CRUD resources — plain APIViews)
# ───────────────────────────────────────────────────────────────────────────

def _parse_report_date(value, default):
    if not value:
        return default
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return default


class DayBookView(APIView):
    """
    Day Book — per-day, per-payment-mode cash/bank reconciliation spanning
    fee collection and the general ledger (payroll, donations, etc).

    Ported from ``core.view_modules.finance_dashboard_views.DayBookReportView``,
    which stays in place unmodified. All aggregation logic lives in
    ``FeeReportingService.day_book`` — this view only parses params and shapes
    the response.
    """
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.transactions.view", write=None),
    ]
    module = "finance"

    @extend_schema(
        description="Day Book report: per-day cash In/Out/Closing balance across fee and general-ledger transactions.",
        parameters=[
            OpenApiParameter(name='from_date', description='Start date (YYYY-MM-DD), defaults to 7 days ago'),
            OpenApiParameter(name='to_date', description='End date (YYYY-MM-DD), defaults to today'),
        ],
    )
    def get(self, request):
        school = request.tenant
        today = date.today()
        date_from = _parse_report_date(request.query_params.get('from_date'), today - timedelta(days=7))
        date_to = _parse_report_date(request.query_params.get('to_date'), today)

        if date_from > date_to:
            return Response({'error': 'from_date must not be after to_date'}, status=status.HTTP_400_BAD_REQUEST)

        report = FeeReportingService(school).day_book(date_from, date_to)
        return Response(report)


class StudentLedgerReportView(APIView):
    """
    Particular-wise Student Transaction Report — a per-student fee
    reconciliation ledger (expected/paid/balance, split PTA vs tuition).

    Ported from ``core.view_modules.finance_dashboard_views
    .ParticularWiseStudentTransactionReportView``, which stays in place
    unmodified. All aggregation logic lives in ``FeeReportingService``
    (``filtered_students_for_ledger_report`` / ``student_ledger_rows`` /
    ``student_ledger_grand_totals`` / ``student_ledger_csv``) — this view only
    parses params, resolves the academic year, and shapes the response.

    Academic year resolution differs from the legacy template view: the
    legacy view uses session-backed ``resolve_selected_year`` tied to a
    Django request/session flow. This API is stateless, so the same helper is
    reused but purely against the ``?academic_year=`` query param with a
    "tenant's active year, else most recent" default — there is no
    session-remembered selection across requests.

    PDF export is descoped here — legacy PDF export remains available only
    on the old template-based view (``?format=pdf``); this endpoint supports
    JSON and ``?format=csv`` only.
    """
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.transactions.view", write=None),
    ]
    module = "finance"

    @extend_schema(
        description="Particular-wise Student Transaction Report: per-student expected/paid/balance, split PTA vs tuition.",
        parameters=[
            OpenApiParameter(name='academic_year', description='Academic year ID; defaults to the active/most recent year'),
            OpenApiParameter(name='student_status', enum=['active', 'all']),
            OpenApiParameter(name='class', description='Course ID, or "all"'),
            OpenApiParameter(name='batch', description='Batch ID, or "all"'),
            OpenApiParameter(name='fee_account', description='Fee category ID, or "all"'),
            OpenApiParameter(name='from_date', description='Filter transactions on/after this date (YYYY-MM-DD)'),
            OpenApiParameter(name='to_date', description='Filter transactions on/before this date (YYYY-MM-DD)'),
            OpenApiParameter(name='with_expected', description='Include PTA/tuition breakdown columns (true/false)'),
            OpenApiParameter(name='format', description='"csv" to download as CSV instead of JSON'),
        ],
    )
    def get(self, request):
        school = request.tenant
        selected_year = resolve_selected_year(request, school)
        if selected_year is None:
            return Response({'error': 'No academic year available for this school'}, status=status.HTTP_404_NOT_FOUND)

        student_status = request.query_params.get('student_status', 'active')
        class_filter = request.query_params.get('class', 'all')
        batch_filter = request.query_params.get('batch', 'all')
        fee_account = request.query_params.get('fee_account', 'all')
        with_expected = str(request.query_params.get('with_expected', '')).lower() in ('1', 'true', 'on', 'yes')

        from_date_obj = None
        to_date_obj = None
        from_date_str = request.query_params.get('from_date')
        to_date_str = request.query_params.get('to_date')
        if from_date_str:
            try:
                from_date_obj = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if to_date_str:
            try:
                to_date_obj = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        service = FeeReportingService(school)
        report = service.student_ledger_report(
            academic_year=selected_year,
            student_status=student_status,
            class_filter=class_filter,
            batch_filter=batch_filter,
            fee_account=fee_account,
            from_date_obj=from_date_obj,
            to_date_obj=to_date_obj,
        )

        if request.query_params.get('format') == 'csv':
            csv_text = FeeReportingService.student_ledger_csv(
                report['rows'], report['grand_totals'], with_expected
            )
            response = HttpResponse(csv_text, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="particular_wise_student_transaction_report.csv"'
            return response

        return Response({
            'academic_year': str(selected_year.id),
            'academic_year_name': selected_year.name,
            'rows': report['rows'],
            'grand_totals': report['grand_totals'],
        })
