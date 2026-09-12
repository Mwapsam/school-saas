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

from rest_framework import viewsets, status, serializers
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter
from decimal import Decimal

from core.models import (
    FamilyInvoice, FinanceFee, FeeCategory, FinanceTransaction,
    FeeDiscount, FineSlab, FinanceTransactionCategory, Student
)
from core.authz.drf import ModuleEnabled, HasPermission
from core.services.fee_reporting_service import FeeReportingService
from core.view_modules.finance_year_context import resolve_selected_year


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class FeeCategorySerializer(serializers.ModelSerializer):
    """Serializer for FeeCategory — charge types (tuition, activity fee, etc.)."""
    class Meta:
        model = FeeCategory
        fields = [
            'id', 'name', 'description', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FeeDiscountSerializer(serializers.ModelSerializer):
    """Serializer for FeeDiscount — discounts applied to fees."""
    fee_category_name = serializers.CharField(source='fee_category.name', read_only=True)

    class Meta:
        model = FeeDiscount
        fields = [
            'id', 'fee_category', 'fee_category_name', 'name',
            'discount_type', 'discount_value', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FineSlabSerializer(serializers.ModelSerializer):
    """Serializer for FineSlab — late payment penalties."""
    class Meta:
        model = FineSlab
        fields = [
            'id', 'name', 'fine_type', 'fine_value', 'applicable_after_days',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FinanceTransactionCategorySerializer(serializers.ModelSerializer):
    """Serializer for FinanceTransactionCategory — transaction types (income, expense, etc.)."""
    class Meta:
        model = FinanceTransactionCategory
        fields = [
            'id', 'name', 'category_type', 'description', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class FinanceTransactionSerializer(serializers.ModelSerializer):
    """Serializer for FinanceTransaction — cash flow transactions."""
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = FinanceTransaction
        fields = [
            'id', 'date', 'category', 'category_name', 'description',
            'amount', 'transaction_type', 'reference_number', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class StudentFeeSerializer(serializers.ModelSerializer):
    """Serializer for FinanceFee — fee assigned to a student."""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    fee_category_name = serializers.CharField(source='fee_category.name', read_only=True)

    class Meta:
        model = FinanceFee
        fields = [
            'id', 'student', 'student_name', 'fee_category', 'fee_category_name',
            'amount', 'due_date', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InvoiceLineItemSerializer(serializers.Serializer):
    """Nested serializer for invoice line items (fees, discounts, fines)."""
    type = serializers.CharField()  # 'fee', 'discount', 'fine'
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for FamilyInvoice — billing invoice sent to families."""
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    # Line items are computed from related FinanceFee + discounts + fines
    line_items = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = FamilyInvoice
        fields = [
            'id', 'invoice_number', 'student', 'student_name', 'due_date',
            'invoice_date', 'status', 'notes', 'line_items', 'total_amount',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'invoice_number', 'created_at', 'updated_at']

    def get_line_items(self, obj):
        """Compute line items from fees, discounts, fines."""
        # This is a simplified version — in production, fetch actual fee ledger
        items = []
        if hasattr(obj.student, 'fees'):
            for fee in obj.student.fees.filter(is_active=True):
                items.append({
                    'type': 'fee',
                    'description': fee.fee_category.name,
                    'amount': str(fee.amount)
                })
        return items

    def get_total_amount(self, obj):
        """Compute total from line items."""
        # Simplified — in production, sum from actual ledger
        total = Decimal('0.00')
        if hasattr(obj.student, 'fees'):
            for fee in obj.student.fees.filter(is_active=True):
                total += fee.amount
        return str(total)


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class FeeCategoryViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class FeeDiscountViewSet(viewsets.ModelViewSet):
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


class FineSlabViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['fine_type', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'applicable_after_days']
    ordering = ['applicable_after_days']


class FinanceTransactionCategoryViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['category_type', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class FinanceTransactionViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['category', 'transaction_type', 'date']
    search_fields = ['description', 'reference_number']
    ordering_fields = ['date', 'amount', 'created_at']
    ordering = ['-date']

    def get_queryset(self):
        return super().get_queryset().select_related('category')

    @extend_schema(
        description="List all finance transactions (paginated, filterable by category/date)",
        parameters=[
            OpenApiParameter(name='category', description='Filter by transaction category'),
            OpenApiParameter(name='transaction_type', enum=['income', 'expense', 'transfer']),
            OpenApiParameter(name='date_from', description='Filter transactions on or after date (YYYY-MM-DD)'),
            OpenApiParameter(name='date_to', description='Filter transactions on or before date (YYYY-MM-DD)'),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class StudentFeeViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['student', 'fee_category', 'is_active']
    search_fields = ['student__full_name']
    ordering_fields = ['student', 'due_date', 'amount']
    ordering = ['due_date']

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

        # Compute balance from FinanceFee
        fees = FinanceFee.objects.filter(student=student, is_active=True, tenant=request.tenant)
        total_due = sum(f.amount for f in fees)

        return Response({
            'student_id': str(student.id),
            'student_name': student.full_name,
            'total_fees': str(total_due),
            'fee_count': fees.count(),
        })


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    Invoice management — billing invoices sent to families.

    Covers:
    - List/create/update invoices
    - Filter by student, status, date
    - Mark invoices as paid
    - Generate invoice PDF
    """
    queryset = FamilyInvoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="finance.invoices.view", write="finance.invoices.manage"),
    ]
    module = "finance"
    filterset_fields = ['student', 'status', 'invoice_date']
    search_fields = ['invoice_number', 'student__full_name']
    ordering_fields = ['invoice_date', 'due_date', 'status']
    ordering = ['-invoice_date']

    def get_queryset(self):
        return super().get_queryset().select_related('student')

    @extend_schema(
        description="List all invoices (paginated, filterable by status/student/date)",
        parameters=[
            OpenApiParameter(name='status', enum=['draft', 'sent', 'paid', 'overdue']),
            OpenApiParameter(name='student', description='Filter by student ID'),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    @extend_schema(
        description="Mark an invoice as paid",
        request=None,
        responses={200: InvoiceSerializer},
    )
    def mark_paid(self, request, pk=None):
        """Mark an invoice as paid."""
        invoice = self.get_object()
        invoice.status = 'paid'
        invoice.save()
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=['post'])
    @extend_schema(
        description="Send invoice to family via email",
        request=None,
        responses={200: {'type': 'object', 'properties': {'sent': {'type': 'boolean'}}}},
    )
    def send(self, request, pk=None):
        """Send invoice to family (mark as sent)."""
        invoice = self.get_object()
        invoice.status = 'sent'
        invoice.save()
        # In production: trigger email send task
        return Response({'sent': True})

    @action(detail=True, methods=['get'])
    @extend_schema(
        description="Download invoice as PDF",
        responses={'application/pdf': None},
    )
    def pdf(self, request, pk=None):
        """Download invoice PDF."""
        invoice = self.get_object()
        # In production: generate/retrieve signed URL to PDF file
        return Response({
            'pdf_url': f'/media/invoices/{invoice.id}.pdf',
            'invoice_number': invoice.invoice_number,
        })


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
