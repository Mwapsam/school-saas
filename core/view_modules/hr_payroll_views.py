"""Payroll categories/groups, employee payroll profiles, payslip generation
(single + group), rejected-payslip handling, payslip display settings, and
payslip reports (including saved report configurations).
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, TemplateView, View

from core.models import (
    Employee, EmployeeDepartment, PayrollCategory, PayrollGroup,
    PayrollGroupComponent, EmployeePayrollProfile, Payslip, PayslipSettings,
)
from core.services.payroll_service import PayrollLookupService, PayslipService, PayslipReportTemplateService
from core.services.exceptions import ServiceException, ValidationException, NotFoundException, DuplicateException, BusinessLogicException
from core.views import _render_paginated_fragment
from core.authz.mixins import PermissionRequiredMixin, require_permission


# --- Payroll categories / groups (lookup CRUD, mirrors HR Settings) ---

PAYROLL_LOOKUP_TEMPLATE = 'core/htmx/hr/payroll_lookup_list_content.html'


def _extract_payroll_fields(request, lookup_key):
    post = request.POST
    if lookup_key == 'payroll_category':
        data = {
            'name': post.get('name', '').strip(),
            'code': post.get('code', '').strip(),
            'category_type': post.get('category_type', 'earning'),
            'calculation_type': post.get('calculation_type', 'fixed'),
            'is_basic_pay': post.get('is_basic_pay') == 'on',
            'taxable': post.get('taxable') == 'on',
        }
        amount = post.get('default_amount')
        pct = post.get('default_percentage')
        data['default_amount'] = Decimal(amount) if amount else None
        data['default_percentage'] = Decimal(pct) if pct else None
        return data
    if lookup_key == 'payroll_group':
        return {
            'name': post.get('name', '').strip(),
            'description': post.get('description', '').strip(),
        }
    return {}


def _render_payroll_lookup_fragment(request, lookup_key):
    tenant = getattr(request, 'tenant', None)
    service = PayrollLookupService(tenant)
    queryset = service.list(lookup_key, search=request.GET.get('search', ''))
    return _render_paginated_fragment(
        request, queryset, PAYROLL_LOOKUP_TEMPLATE, 'items', paginate_by=15,
        extra_context={'lookup_key': lookup_key},
    )


class PayrollSettingsLandingView(PermissionRequiredMixin, TemplateView):
    required_permission = 'hr.payroll.manage'
    template_name = 'core/hr/payroll/settings_landing.html'



class PayrollLookupListView(PermissionRequiredMixin, ListView):
    required_permission = 'hr.payroll.manage'
    paginate_by = 15
    context_object_name = 'items'

    def dispatch(self, request, *args, **kwargs):
        self.lookup_key = kwargs.get('lookup_key')
        if self.lookup_key not in ('payroll_category', 'payroll_group'):
            raise Http404('Unknown payroll lookup type')
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [PAYROLL_LOOKUP_TEMPLATE]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        return PayrollLookupService(tenant).list(self.lookup_key, search=self.request.GET.get('search', ''))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lookup_key'] = self.lookup_key
        return context


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payroll_lookup_create_api(request, lookup_key):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        data = _extract_payroll_fields(request, lookup_key)
        if not data.get('name'):
            return JsonResponse({'name': ['This field is required']}, status=400)
        PayrollLookupService(tenant).create(lookup_key, user=request.user, **data)
        return HttpResponse(_render_payroll_lookup_fragment(request, lookup_key))
    except DuplicateException as e:
        return JsonResponse({'name': [str(e.message)]}, status=400)
    except (ValidationException, InvalidOperation) as e:
        return JsonResponse({'error': [str(e)]}, status=400)
    except ServiceException as e:
        return JsonResponse({'error': [str(e.message)]}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payroll_lookup_update_api(request, lookup_key, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        data = _extract_payroll_fields(request, lookup_key)
        if not data.get('name'):
            return JsonResponse({'name': ['This field is required']}, status=400)
        PayrollLookupService(tenant).update(lookup_key, pk, user=request.user, **data)
        return HttpResponse(_render_payroll_lookup_fragment(request, lookup_key))
    except NotFoundException as e:
        return JsonResponse({'error': [str(e.message)]}, status=404)
    except DuplicateException as e:
        return JsonResponse({'name': [str(e.message)]}, status=400)
    except (ValidationException, InvalidOperation) as e:
        return JsonResponse({'error': [str(e)]}, status=400)
    except ServiceException as e:
        return JsonResponse({'error': [str(e.message)]}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payroll_lookup_toggle_status_api(request, lookup_key, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        PayrollLookupService(tenant).toggle_status(lookup_key, pk)
        return HttpResponse(_render_payroll_lookup_fragment(request, lookup_key))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payroll_lookup_delete_api(request, lookup_key, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        PayrollLookupService(tenant).delete(lookup_key, pk)
        return HttpResponse(_render_payroll_lookup_fragment(request, lookup_key))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)
    except ServiceException as e:
        return JsonResponse({'error': str(e.message)}, status=400)


# --- Payroll group detail (component management) ---

class PayrollGroupDetailView(PermissionRequiredMixin, TemplateView):
    required_permission = 'hr.payroll.manage'
    template_name = 'core/hr/payroll/group_detail.html'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        group = PayrollGroup.objects.get(tenant=tenant, id=kwargs['pk'])
        context['group'] = group
        context['components'] = PayrollLookupService(tenant).get_group_components(group.id)
        context['categories'] = PayrollCategory.objects.filter(tenant=tenant, status=True)
        return context


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payroll_group_component_add_api(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        amount = request.POST.get('override_amount')
        pct = request.POST.get('override_percentage')
        PayrollLookupService(tenant).add_component_to_group(
            pk, request.POST.get('payroll_category_id'),
            override_amount=Decimal(amount) if amount else None,
            override_percentage=Decimal(pct) if pct else None,
        )
        return _render_group_components(request, tenant, pk)
    except (ValidationException, DuplicateException, NotFoundException) as e:
        return JsonResponse({'error': str(e.message)}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payroll_group_component_remove_api(request, pk, component_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        PayrollLookupService(tenant).remove_component_from_group(component_id)
        return _render_group_components(request, tenant, pk)
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


def _render_group_components(request, tenant, group_id):
    components = PayrollLookupService(tenant).get_group_components(group_id)
    html = render_to_string('core/htmx/hr/payroll_group_components.html', {
        'group_id': group_id, 'components': components,
    })
    return HttpResponse(html)


# --- Employee payroll profile (tab on the employee edit modal) ---

def _render_employee_payroll_fragment(tenant, employee_id):
    employee = Employee.objects.get(tenant=tenant, id=employee_id)
    profile = EmployeePayrollProfile.objects.filter(tenant=tenant, employee=employee).first()
    return render_to_string('core/htmx/hr/employee_payroll_tab.html', {
        'employee_id': employee_id,
        'profile': profile,
        'payroll_groups': PayrollGroup.objects.filter(tenant=tenant, status=True),
    })


@require_http_methods(["GET"])
@login_required
@require_permission('hr.payroll.view')
def employee_payroll_profile_tab(request, employee_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    return HttpResponse(_render_employee_payroll_fragment(tenant, employee_id))


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def employee_payroll_profile_update_api(request, employee_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    employee = Employee.objects.get(tenant=tenant, id=employee_id)
    basic_pay = request.POST.get('basic_pay_amount') or 0
    payroll_group_id = request.POST.get('payroll_group_id') or None
    effective_date = request.POST.get('effective_date') or None

    EmployeePayrollProfile.objects.update_or_create(
        tenant=tenant, employee=employee,
        defaults={
            'payroll_group_id': payroll_group_id,
            'basic_pay_amount': Decimal(basic_pay),
            'bank_name': request.POST.get('bank_name', ''),
            'bank_account_number': request.POST.get('bank_account_number', ''),
            'bank_branch': request.POST.get('bank_branch', ''),
            'effective_date': effective_date,
        },
    )
    return HttpResponse(_render_employee_payroll_fragment(tenant, employee_id))


# --- Payroll runs (batch payslip generation, grouped by pay period) ---

class PayrollRunsView(PermissionRequiredMixin, TemplateView):
    """A 'payroll run' is the set of payslips sharing a (group, period). This
    screen lists past runs with status counts and offers a generate form.
    Backed entirely by existing Payslip data + payslip_generate_group_api."""
    required_permission = 'hr.payroll.manage'
    template_name = 'core/hr/payroll/payroll_runs.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['payroll_groups'] = PayrollGroup.objects.filter(tenant=tenant, status=True)
            runs = (
                Payslip.objects.filter(tenant=tenant)
                .values('period_start', 'period_end', 'payroll_group_name_snapshot')
                .annotate(
                    total=Count('id'),
                    generated=Count('id', filter=Q(status='generated')),
                    approved=Count('id', filter=Q(status='approved')),
                    rejected=Count('id', filter=Q(status='rejected')),
                    paid=Count('id', filter=Q(status='paid')),
                )
                .order_by('-period_start', 'payroll_group_name_snapshot')
            )
            context['runs'] = runs
        context['back_url'] = reverse('core:hr_dashboard')
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Payroll Runs'},
        ]
        return context


# --- Payslip generation ---

class PayslipGenerateView(PermissionRequiredMixin, TemplateView):
    required_permission = 'hr.payroll.manage'
    template_name = 'core/hr/payroll/payslip_generate.html'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['employees'] = Employee.objects.filter(tenant=tenant, status=True).order_by('first_name')
            context['payroll_groups'] = PayrollGroup.objects.filter(tenant=tenant, status=True)
        return context


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payslip_generate_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        start = datetime.strptime(request.POST.get('period_start', ''), '%Y-%m-%d').date()
        end = datetime.strptime(request.POST.get('period_end', ''), '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Valid period start/end dates are required'}, status=400)

    try:
        payslip = PayslipService(tenant).generate_payslip(
            request.POST.get('employee_id'), start, end, generated_by=request.user,
        )
        return JsonResponse({'success': True, 'payslip_id': str(payslip.id), 'net_pay': str(payslip.net_pay)})
    except (BusinessLogicException, NotFoundException) as e:
        return JsonResponse({'error': str(e.message)}, status=400)
    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Employee not found'}, status=404)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payslip_generate_group_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        start = datetime.strptime(request.POST.get('period_start', ''), '%Y-%m-%d').date()
        end = datetime.strptime(request.POST.get('period_end', ''), '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Valid period start/end dates are required'}, status=400)

    payslips, errors = PayslipService(tenant).generate_payslips_for_group(
        request.POST.get('payroll_group_id'), start, end, generated_by=request.user,
    )
    return JsonResponse({'success': True, 'generated': len(payslips), 'errors': errors})


# --- Payslip list (all statuses, including rejected) ---

def _filtered_payslips(request, tenant):
    filters = {
        'payroll_group_id': request.GET.get('payroll_group') or None,
        'department_id': request.GET.get('department') or None,
        'status': request.GET.get('status') or None,
    }
    return PayslipService(tenant).get_payslip_report(filters)


class PayslipListView(PermissionRequiredMixin, ListView):
    required_permission = 'hr.payroll.view'
    template_name = 'core/hr/payroll/payslip_list.html'
    htmx_template_name = 'core/htmx/hr/payslip_list_content.html'
    context_object_name = 'payslips'
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get('HX-Request') == 'true'
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        return _filtered_payslips(self.request, tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['payroll_groups'] = PayrollGroup.objects.filter(tenant=tenant, status=True)
            context['departments'] = EmployeeDepartment.objects.filter(tenant=tenant, status=True)
        return context


def _render_payslip_list_fragment(request, tenant):
    return _render_paginated_fragment(
        request, _filtered_payslips(request, tenant), 'core/htmx/hr/payslip_list_content.html', 'payslips', paginate_by=15,
    )


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payslip_approve_api(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        PayslipService(tenant).approve_payslip(pk, approved_by=request.user)
        return HttpResponse(_render_payslip_list_fragment(request, tenant))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payslip_reject_api(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        PayslipService(tenant).reject_payslip(pk, request.POST.get('reason', ''))
        return HttpResponse(_render_payslip_list_fragment(request, tenant))
    except (NotFoundException, BusinessLogicException) as e:
        return JsonResponse({'error': str(e.message)}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payslip_regenerate_api(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        PayslipService(tenant).regenerate_payslip(pk, generated_by=request.user)
        return HttpResponse(_render_payslip_list_fragment(request, tenant))
    except (NotFoundException, BusinessLogicException) as e:
        return JsonResponse({'error': str(e.message)}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payslip_mark_paid_api(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        PayslipService(tenant).mark_paid(pk)
        return HttpResponse(_render_payslip_list_fragment(request, tenant))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payslip_unmark_paid_api(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)
    try:
        PayslipService(tenant).unmark_paid(pk)
        return HttpResponse(_render_payslip_list_fragment(request, tenant))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


class PayslipPDFView(PermissionRequiredMixin, View):
    required_permission = 'hr.payroll.view'
    def get(self, request, pk):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            raise Http404('School not found')

        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
        from core.models import CurrencyConfiguration

        payslip = Payslip.objects.select_related('employee', 'payroll_group').prefetch_related('line_items').get(
            tenant=tenant, id=pk,
        )
        settings = PayslipSettings.get_settings(tenant)
        currency = CurrencyConfiguration.get_active_currency(tenant)
        profile = EmployeePayrollProfile.objects.filter(tenant=tenant, employee=payslip.employee).first()

        def fmt(amount):
            return currency.format_amount(amount) if currency else f"{amount:.2f}"

        html_content = render_to_string('core/hr/payroll/payslip_pdf.html', {
            'school': tenant,
            'payslip': payslip,
            'settings': settings,
            'profile': profile,
            'earnings': [li for li in payslip.line_items.all() if li.category_type_snapshot == 'earning'],
            'deductions': [li for li in payslip.line_items.all() if li.category_type_snapshot == 'deduction'],
            'gross_display': fmt(payslip.gross_earnings),
            'deductions_display': fmt(payslip.total_deductions),
            'net_display': fmt(payslip.net_pay),
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="payslip_{payslip.employee.employee_number}_{payslip.period_start}.pdf"'
        return response


class PayslipSettingsView(PermissionRequiredMixin, TemplateView):
    required_permission = 'hr.payroll.manage'
    template_name = 'core/hr/payroll/payslip_settings.html'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['settings'] = PayslipSettings.get_settings(tenant)
        return context


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payslip_settings_update_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    settings = PayslipSettings.get_settings(tenant)
    for field in ('show_company_logo', 'show_bank_details', 'show_leave_balance', 'show_ytd_earnings', 'show_employee_photo'):
        setattr(settings, field, request.POST.get(field) == 'on')
    settings.footer_text = request.POST.get('footer_text', '')
    settings.save()
    return JsonResponse({'success': True})


# --- Payslip reports + saved report templates ---

class PayslipReportView(PermissionRequiredMixin, TemplateView):
    required_permission = 'hr.payroll.manage'
    template_name = 'core/hr/payroll/payslip_report.html'


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['payroll_groups'] = PayrollGroup.objects.filter(tenant=tenant, status=True)
            context['departments'] = EmployeeDepartment.objects.filter(tenant=tenant, status=True)
            context['templates'] = PayslipReportTemplateService(tenant).list_templates()
            filters = {
                'payroll_group_id': self.request.GET.get('payroll_group') or None,
                'department_id': self.request.GET.get('department') or None,
                'status': self.request.GET.get('status') or None,
            }
            context['rows'] = PayslipService(tenant).get_payslip_report(filters)
            context['applied_filters'] = filters
        return context


@require_http_methods(["POST"])
@login_required
@require_permission('hr.payroll.manage')
def payslip_report_template_save_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    import json
    filters = {
        'payroll_group_id': request.POST.get('payroll_group_id') or None,
        'department_id': request.POST.get('department_id') or None,
        'status': request.POST.get('status') or None,
    }
    columns = request.POST.getlist('columns') or ['employee', 'department', 'gross_earnings', 'total_deductions', 'net_pay', 'status']

    try:
        PayslipReportTemplateService(tenant).save_template(
            name=request.POST.get('name', '').strip(),
            filters=filters, columns=columns, created_by=request.user, user=request.user,
        )
        return JsonResponse({'success': True})
    except ServiceException as e:
        return JsonResponse({'error': str(e.message)}, status=400)


@require_http_methods(["GET"])
@login_required
@require_permission('hr.payroll.view')
def payslip_report_template_run_api(request, pk):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    from core.models import PayslipReportTemplate
    template = PayslipReportTemplate.objects.get(tenant=tenant, id=pk)
    rows = PayslipService(tenant).get_payslip_report(template.filters)
    html = render_to_string('core/htmx/hr/payslip_report_results.html', {
        'rows': rows, 'columns': template.columns,
    })
    return HttpResponse(html)
