from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from core.models import (
    Employee,
    EmployeeDepartment,
    PayrollCategory,
    PayrollGroup,
    PayrollGroupComponent,
    EmployeePayrollProfile,
    Payslip,
    PayslipLineItem,
    PayslipSettings,
    PayslipReportTemplate,
)
from .base import TenantAwareService
from .exceptions import ValidationException, NotFoundException, DuplicateException, BusinessLogicException
from .logging_service import ServiceLogger, logged_operation


class PayrollLookupService:
    """CRUD for PayrollCategory and PayrollGroup — same simple-lookup shape
    as HRSettingsService, plus PayrollGroupComponent management.
    """

    LOOKUP_MODELS = {
        'payroll_category': PayrollCategory,
        'payroll_group': PayrollGroup,
    }

    def __init__(self, tenant):
        self.tenant = tenant
        self.logger = ServiceLogger('payroll_lookup', tenant)

    def _model(self, lookup_key: str):
        try:
            return self.LOOKUP_MODELS[lookup_key]
        except KeyError:
            raise ValidationException(f"Unknown payroll lookup type '{lookup_key}'")

    def _get(self, model, obj_id: Any):
        try:
            return model.objects.get(tenant=self.tenant, id=obj_id)
        except (model.DoesNotExist, ValueError, TypeError):
            raise NotFoundException(f"{model.__name__} with id {obj_id} not found")

    def list(self, lookup_key: str, search: Optional[str] = None):
        model = self._model(lookup_key)
        queryset = model.objects.filter(tenant=self.tenant)
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by('name')

    @logged_operation(action='create', resource_type='payroll_lookup', log_result=True)
    def create(self, lookup_key: str, user=None, **data: Dict[str, Any]):
        model = self._model(lookup_key)
        name = data.get('name')
        if name and model.objects.filter(tenant=self.tenant, name__iexact=name).exists():
            raise DuplicateException(f"{model.__name__} with name '{name}' already exists")

        if lookup_key == 'payroll_category' and data.get('is_basic_pay'):
            PayrollCategory.objects.filter(tenant=self.tenant, is_basic_pay=True).update(is_basic_pay=False)

        instance = model(tenant=self.tenant, **data)
        instance.full_clean()
        instance.save()
        return instance

    @logged_operation(action='update', resource_type='payroll_lookup', log_result=True)
    def update(self, lookup_key: str, obj_id: Any, user=None, **data: Dict[str, Any]):
        model = self._model(lookup_key)
        instance = self._get(model, obj_id)

        name = data.get('name')
        if name and model.objects.filter(tenant=self.tenant, name__iexact=name).exclude(id=obj_id).exists():
            raise DuplicateException(f"{model.__name__} with name '{name}' already exists")

        if lookup_key == 'payroll_category' and data.get('is_basic_pay'):
            PayrollCategory.objects.filter(tenant=self.tenant, is_basic_pay=True).exclude(id=obj_id).update(is_basic_pay=False)

        for field, value in data.items():
            setattr(instance, field, value)
        instance.full_clean()
        instance.save()
        return instance

    def toggle_status(self, lookup_key: str, obj_id: Any):
        model = self._model(lookup_key)
        instance = self._get(model, obj_id)
        instance.status = not instance.status
        instance.save(update_fields=['status'])
        return instance

    def delete(self, lookup_key: str, obj_id: Any) -> None:
        model = self._model(lookup_key)
        instance = self._get(model, obj_id)
        instance.delete()

    # --- Payroll group components ---

    def get_group_components(self, payroll_group_id: Any):
        return PayrollGroupComponent.objects.filter(
            tenant=self.tenant, payroll_group_id=payroll_group_id
        ).select_related('payroll_category').order_by('order')

    @logged_operation(action='add_component', resource_type='payroll_group', log_result=True)
    def add_component_to_group(self, payroll_group_id: Any, payroll_category_id: Any, user=None,
                                override_amount=None, override_percentage=None) -> PayrollGroupComponent:
        group = self._get(PayrollGroup, payroll_group_id)
        category = self._get(PayrollCategory, payroll_category_id)
        if PayrollGroupComponent.objects.filter(tenant=self.tenant, payroll_group=group, payroll_category=category).exists():
            raise DuplicateException(f"'{category.name}' is already part of this payroll group")
        order = PayrollGroupComponent.objects.filter(tenant=self.tenant, payroll_group=group).count()
        return PayrollGroupComponent.objects.create(
            tenant=self.tenant, payroll_group=group, payroll_category=category,
            override_amount=override_amount, override_percentage=override_percentage, order=order,
        )

    def update_component_override(self, component_id: Any, override_amount=None, override_percentage=None) -> PayrollGroupComponent:
        component = self._get(PayrollGroupComponent, component_id)
        component.override_amount = override_amount
        component.override_percentage = override_percentage
        component.save()
        return component

    def remove_component_from_group(self, component_id: Any) -> None:
        self._get(PayrollGroupComponent, component_id).delete()


class PayslipService(TenantAwareService[Payslip]):
    def __init__(self, tenant):
        super().__init__(Payslip, tenant)
        self.logger = ServiceLogger('payslip', tenant)

    def _get_profile(self, employee: Employee) -> EmployeePayrollProfile:
        try:
            return employee.payroll_profile
        except EmployeePayrollProfile.DoesNotExist:
            raise BusinessLogicException(
                f"{employee} has no payroll profile set up (basic pay / payroll group)"
            )

    def _compute_line_items(self, profile: EmployeePayrollProfile) -> List[Dict[str, Any]]:
        if not profile.payroll_group:
            raise BusinessLogicException(f"{profile.employee} is not assigned to a payroll group")

        components = PayrollGroupComponent.objects.filter(
            tenant=self.tenant, payroll_group=profile.payroll_group, is_active=True
        ).select_related('payroll_category').order_by('order')

        line_items = []
        for component in components:
            category = component.payroll_category
            if category.is_basic_pay:
                # The basic-pay category's amount IS the employee's own
                # basic_pay_amount — that's the whole point of the flag,
                # not the category's own tenant-wide default_amount.
                amount = profile.basic_pay_amount
            elif component.override_amount is not None:
                amount = component.override_amount
            elif component.override_percentage is not None:
                amount = (component.override_percentage / Decimal('100')) * profile.basic_pay_amount
            elif category.calculation_type == 'percentage' and category.default_percentage is not None:
                amount = (category.default_percentage / Decimal('100')) * profile.basic_pay_amount
            else:
                amount = category.default_amount or Decimal('0')

            line_items.append({
                'payroll_category': category,
                'category_name_snapshot': category.name,
                'category_type_snapshot': category.category_type,
                'amount': amount,
                'order': component.order,
            })
        return line_items

    @logged_operation(action='generate', resource_type='payslip', log_result=True)
    @transaction.atomic
    def generate_payslip(self, employee_id: Any, period_start: date, period_end: date, generated_by=None, user=None) -> Payslip:
        employee = Employee.objects.get(id=employee_id, tenant=self.tenant)
        profile = self._get_profile(employee)
        line_items = self._compute_line_items(profile)

        gross = sum((li['amount'] for li in line_items if li['category_type_snapshot'] == 'earning'), Decimal('0'))
        deductions = sum((li['amount'] for li in line_items if li['category_type_snapshot'] == 'deduction'), Decimal('0'))
        net = gross - deductions

        payslip, created = Payslip.objects.get_or_create(
            tenant=self.tenant, employee=employee, period_start=period_start, period_end=period_end,
            defaults={
                'payroll_group': profile.payroll_group,
                'payroll_group_name_snapshot': profile.payroll_group.name,
                'basic_pay_snapshot': profile.basic_pay_amount,
                'gross_earnings': gross,
                'total_deductions': deductions,
                'net_pay': net,
                'status': 'generated',
                'generated_by': generated_by,
            },
        )
        if not created:
            if payslip.status == 'paid':
                raise BusinessLogicException("Cannot regenerate a payslip that has already been marked paid")
            payslip.payroll_group = profile.payroll_group
            payslip.payroll_group_name_snapshot = profile.payroll_group.name
            payslip.basic_pay_snapshot = profile.basic_pay_amount
            payslip.gross_earnings = gross
            payslip.total_deductions = deductions
            payslip.net_pay = net
            payslip.status = 'generated'
            payslip.rejection_reason = ''
            payslip.version += 1
            payslip.generated_by = generated_by
            payslip.save()
            payslip.line_items.all().delete()

        PayslipLineItem.objects.bulk_create([
            PayslipLineItem(tenant=self.tenant, payslip=payslip, **li) for li in line_items
        ])
        return payslip

    def generate_payslips_for_group(self, payroll_group_id: Any, period_start: date, period_end: date, generated_by=None) -> List[Payslip]:
        profiles = EmployeePayrollProfile.objects.filter(
            tenant=self.tenant, payroll_group_id=payroll_group_id, status=True, employee__status=True
        ).select_related('employee')

        payslips = []
        errors = []
        for profile in profiles:
            try:
                payslips.append(self.generate_payslip(profile.employee_id, period_start, period_end, generated_by=generated_by))
            except BusinessLogicException as e:
                errors.append(f"{profile.employee}: {e.message}")
        return payslips, errors

    @logged_operation(action='reject', resource_type='payslip', log_result=True)
    def reject_payslip(self, payslip_id: Any, reason: str, user=None) -> Payslip:
        payslip = self.get_by_id(payslip_id)
        if payslip.status == 'paid':
            raise BusinessLogicException("A paid payslip cannot be rejected")
        payslip.status = 'rejected'
        payslip.rejection_reason = reason
        payslip.save()
        return payslip

    @logged_operation(action='approve', resource_type='payslip', log_result=True)
    def approve_payslip(self, payslip_id: Any, approved_by=None, user=None) -> Payslip:
        payslip = self.get_by_id(payslip_id)
        payslip.status = 'approved'
        payslip.approved_by = approved_by
        payslip.approved_at = timezone.now()
        payslip.save()
        return payslip

    @logged_operation(action='mark_paid', resource_type='payslip', log_result=True)
    def mark_paid(self, payslip_id: Any, user=None) -> Payslip:
        payslip = self.get_by_id(payslip_id)
        payslip.status = 'paid'
        payslip.paid_at = timezone.now()
        payslip.save()
        return payslip

    @logged_operation(action='unmark_paid', resource_type='payslip', log_result=True)
    def unmark_paid(self, payslip_id: Any, user=None) -> Payslip:
        payslip = self.get_by_id(payslip_id)
        payslip.status = 'approved'
        payslip.paid_at = None
        payslip.save()
        return payslip

    def regenerate_payslip(self, payslip_id: Any, generated_by=None) -> Payslip:
        payslip = self.get_by_id(payslip_id)
        return self.generate_payslip(payslip.employee_id, payslip.period_start, payslip.period_end, generated_by=generated_by)

    def get_payslip_report(self, filters: Dict[str, Any]):
        queryset = Payslip.objects.filter(tenant=self.tenant).select_related('employee', 'payroll_group')

        if filters.get('payroll_group_id'):
            queryset = queryset.filter(payroll_group_id=filters['payroll_group_id'])
        if filters.get('department_id'):
            queryset = queryset.filter(employee__employee_department_id=filters['department_id'])
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        if filters.get('period_start'):
            queryset = queryset.filter(period_start__gte=filters['period_start'])
        if filters.get('period_end'):
            queryset = queryset.filter(period_end__lte=filters['period_end'])

        return queryset.order_by('-period_start', 'employee__first_name')


class PayslipReportTemplateService(TenantAwareService[PayslipReportTemplate]):
    def __init__(self, tenant):
        super().__init__(PayslipReportTemplate, tenant)
        self.logger = ServiceLogger('payslip_report_template', tenant)

    def list_templates(self):
        return self.get_base_queryset().order_by('-created_at')

    @logged_operation(action='save', resource_type='payslip_report_template', log_result=True)
    def save_template(self, name: str, filters: Dict[str, Any], columns: List[str], created_by=None, user=None) -> PayslipReportTemplate:
        return self.create(name=name, filters=filters, columns=columns, created_by=created_by)
