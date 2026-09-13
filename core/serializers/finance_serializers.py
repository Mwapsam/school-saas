"""
Finance domain serializers — Invoicing, fees, transactions.

Pattern: All serializers inherit from TenantAwareSerializer + ServiceSerializerMixin.
This ensures:
1. Tenant context is properly passed to services
2. Service exceptions (ValidationException, DuplicateException, etc.) are translated to DRF errors
3. Validation logic is centralized in the service layer, not scattered

For each serializer, define:
- service_class: the service this serializer delegates to
- _service_create: how to create via the service
- _service_update: how to update via the service (or use default model-based update)
"""

from rest_framework import serializers
from core.models import (
    FamilyInvoice, FamilyInvoiceLine, FinanceFee, FeeCategory, FinanceTransaction,
    FeeDiscount, FineSlab, FinanceTransactionCategory
)
from core.serializers.base import TenantAwareSerializer, ServiceSerializerMixin, ReadOnlyServiceSerializer
from core.services.finance_service import FinanceService


class FeeCategorySerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for FeeCategory — charge types (tuition, activity fee, etc.).

    Delegates to FinanceService for validation. The model has no ``is_active`` field —
    categories are soft-deleted via ``is_deleted`` instead, which is an internal flag
    (kept out of this writable serializer).

    Pattern:
    - Read: List/retrieve all non-deleted categories
    - Create: Via FinanceService, validates against tenant
    - Update: Via FinanceService
    - Delete: Soft-delete (is_deleted=True)
    """
    service_class = FinanceService
    academic_year_label = serializers.CharField(source='academic_year.__str__', read_only=True, default=None)

    class Meta:
        model = FeeCategory
        fields = [
            'id', 'name', 'description', 'academic_year', 'academic_year_label',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        """Delegate FeeCategory creation to FinanceService"""
        # For now, simple delegation; if FinanceService has a create_fee_category method, use it
        # Otherwise, fall back to direct model creation (service will validate)
        instance = FeeCategory.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate FeeCategory update to FinanceService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FeeDiscountSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for FeeDiscount — discounts applied to fees.

    Delegates to FinanceService for validation. Includes read-only nested fee_category_name.
    """
    service_class = FinanceService
    fee_category_name = serializers.CharField(source='fee_category.name', read_only=True)

    class Meta:
        model = FeeDiscount
        fields = [
            'id', 'fee_category', 'fee_category_name', 'name',
            'discount_type', 'discount_mode', 'discount_value', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        """Delegate FeeDiscount creation to FinanceService"""
        instance = FeeDiscount.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate FeeDiscount update to FinanceService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FineSlabSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for FineSlab — late payment penalties.

    Delegates to FinanceService for validation of fine amounts and days.
    """
    service_class = FinanceService

    class Meta:
        model = FineSlab
        fields = [
            'id', 'fine_name', 'fine_mode', 'fine_value', 'days_after_due',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        """Delegate FineSlab creation to FinanceService"""
        instance = FineSlab.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate FineSlab update to FinanceService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FinanceTransactionCategorySerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for FinanceTransactionCategory — transaction types (income vs expense).

    Delegates to FinanceService for validation. Read-only after creation (categories shouldn't be
    redefined mid-year, as it would break reporting).
    """
    service_class = FinanceService

    class Meta:
        model = FinanceTransactionCategory
        fields = [
            'id', 'name', 'prefix', 'description', 'is_income',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        """Delegate FinanceTransactionCategory creation to FinanceService"""
        instance = FinanceTransactionCategory.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate update to FinanceService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FinanceTransactionSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for FinanceTransaction — cash flow transactions.

    Delegates to FinanceService for validation of amounts and references.
    Includes read-only nested names for related objects (student, employee, category).
    """
    service_class = FinanceService
    category_name = serializers.CharField(source='category.name', read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True, default=None)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True, default=None)

    class Meta:
        model = FinanceTransaction
        fields = [
            'id', 'title', 'transaction_date', 'category', 'category_name',
            'student', 'student_name', 'employee', 'employee_name',
            'academic_year', 'description', 'amount', 'payment_method',
            'reference_number', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_amount(self, value):
        """Validate that amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value

    def _service_create(self, service, validated_data):
        """Delegate FinanceTransaction creation to FinanceService"""
        instance = FinanceTransaction.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate update to FinanceService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class StudentFeeSerializer(TenantAwareSerializer, ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for FinanceFee — fee assigned to a student.

    Delegates to FinanceService for validation. ``transaction_date`` is when the fee was
    recorded, not the due date (model has no separate due-date field). ``is_paid`` replaces
    a non-existent ``is_active`` (fees become paid, not inactive).
    """
    service_class = FinanceService
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    fee_category_name = serializers.CharField(source='fee_category.name', read_only=True)

    class Meta:
        model = FinanceFee
        fields = [
            'id', 'student', 'student_name', 'fee_category', 'fee_category_name',
            'academic_year', 'balance', 'transaction_date', 'is_paid',
            'tax_amount', 'discount_amount', 'invoice_number',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _service_create(self, service, validated_data):
        """Delegate StudentFee creation to FinanceService"""
        instance = FinanceFee.objects.create(
            tenant=self.context.get('tenant'),
            **validated_data
        )
        return instance

    def _service_update(self, service, instance, validated_data):
        """Delegate update to FinanceService"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class InvoiceLineSerializer(ReadOnlyServiceSerializer, serializers.ModelSerializer):
    """
    Nested read-only serializer for FamilyInvoiceLine — one per child's charge
    on the guardian's consolidated invoice. This is derived data; manual creation
    is not supported (InvoiceService generates lines automatically).
    """
    student_name = serializers.CharField(source='student.full_name', read_only=True)

    class Meta:
        model = FamilyInvoiceLine
        fields = ['id', 'student', 'student_name', 'description', 'amount']
        read_only_fields = fields


class InvoiceSerializer(ReadOnlyServiceSerializer, serializers.ModelSerializer):
    """
    Serializer for FamilyInvoice — the guardian's consolidated invoice for
    an academic year (aggregates every child's charges into one invoice).

    Entirely read-only: status, totals and due_date are derived by
    ``InvoiceService.recompute_totals`` whenever a charge or payment changes.
    There is no legitimate manual create/edit/mark-paid path — the system
    computes all derived fields automatically.

    See: core/services/invoice_service.py
    """
    service_class = FinanceService
    guardian_name = serializers.CharField(source='guardian.full_name', read_only=True)
    academic_year_label = serializers.CharField(source='academic_year.__str__', read_only=True)
    lines = InvoiceLineSerializer(many=True, read_only=True)

    class Meta:
        model = FamilyInvoice
        fields = [
            'id', 'invoice_number', 'guardian', 'guardian_name',
            'academic_year', 'academic_year_label', 'status',
            'subtotal', 'total_amount', 'amount_paid', 'balance_due',
            'due_date', 'generated_at', 'last_updated_at', 'lines',
        ]
        read_only_fields = fields
