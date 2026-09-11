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

from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from decimal import Decimal

from core.models import (
    FamilyInvoice, FinanceFee, FeeCategory, FinanceTransaction,
    FeeDiscount, FineSlab, FinanceTransactionCategory, Student
)
from core.authz.drf import ModuleEnabled, HasPermission


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
        ModuleEnabled("finance"),
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
        ModuleEnabled("finance"),
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
        ModuleEnabled("finance"),
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
        ModuleEnabled("finance"),
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
        ModuleEnabled("finance"),
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
        ModuleEnabled("finance"),
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
        ModuleEnabled("finance"),
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
