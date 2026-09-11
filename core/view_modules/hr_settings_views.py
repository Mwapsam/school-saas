"""HR Settings: CRUD screens for the employee lookup tables (Category,
Position, Department, Grade), Leave Types, and the tenant-wide employee
working-day settings singleton.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, TemplateView

from core.authz.mixins import PermissionRequiredMixin, require_permission
from core.models import Employee, EmployeeLeave, FeeReceiptSettings, Payslip
from core.services.employee_service import EmployeeService
from core.services.hr_settings_service import HRSettingsService, WorkingDaySettingsService
from core.services.exceptions import ServiceException, ValidationException, NotFoundException, DuplicateException
from core.views import _render_paginated_fragment

# Any of these means "can see the HR area" (the hub landing page).
HR_ANY = [
    'hr.employee.view', 'hr.leave.view', 'hr.attendance.manage',
    'hr.payroll.view', 'hr.settings.manage',
]

# Per-lookup form field whitelist + template locations. Kept as one small
# config dict rather than five near-identical view classes, since the only
# real difference between these screens is which fields the form collects.
LOOKUP_CONFIG = {
    'category': {'label': 'Employee Category'},
    'position': {'label': 'Employee Position'},
    'department': {'label': 'Employee Department'},
    'grade': {'label': 'Employee Grade'},
    'leave_type': {'label': 'Leave Type'},
}

LOOKUP_LIST_TEMPLATE = 'core/htmx/hr/lookup_list_content.html'
LOOKUP_TEMPLATES = {key: LOOKUP_LIST_TEMPLATE for key in LOOKUP_CONFIG}


def _extract_fields(request, lookup_key):
    post = request.POST
    if lookup_key == 'category':
        return {
            'name': post.get('name', '').strip(),
            'prefix': post.get('prefix', '').strip(),
        }
    if lookup_key == 'position':
        return {
            'name': post.get('name', '').strip(),
            'employee_category_id': post.get('employee_category_id') or None,
        }
    if lookup_key == 'department':
        return {
            'name': post.get('name', '').strip(),
            'code': post.get('code', '').strip(),
        }
    if lookup_key == 'grade':
        max_hours_day = post.get('max_hours_day')
        max_hours_week = post.get('max_hours_week')
        return {
            'name': post.get('name', '').strip(),
            'priority': int(post.get('priority') or 0),
            'max_hours_day': int(max_hours_day) if max_hours_day else None,
            'max_hours_week': int(max_hours_week) if max_hours_week else None,
        }
    if lookup_key == 'leave_type':
        return {
            'name': post.get('name', '').strip(),
            'code': post.get('code', '').strip(),
            'default_annual_days': int(post.get('default_annual_days') or 0),
            'is_paid': post.get('is_paid') == 'on',
        }
    return {}


class HRSettingsLandingView(PermissionRequiredMixin, TemplateView):
    template_name = 'core/hr/settings/landing.html'
    required_permission = 'hr.settings.manage'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lookup_labels'] = {key: cfg['label'] for key, cfg in LOOKUP_CONFIG.items()}
        context['weekday_choices'] = [
            (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
            (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
        ]
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['categories'] = HRSettingsService(tenant).list('category')
            context['working_day_settings'] = WorkingDaySettingsService(tenant).get_settings()
        return context


def _hr_dashboard_sections():
    """The HR navigation model — functional domains, each a group of tiles.
    Shared by the dashboard and (a subset) by the Reports index."""
    return [
        {'title': 'Employees', 'tiles': [
            {'icon': 'fa-id-badge', 'title': 'All Employees', 'description': 'Onboard, edit and manage teaching and non-teaching staff', 'url': reverse('core:teacher_list')},
            {'icon': 'fa-chalkboard-teacher', 'title': 'Subject Assignments', 'description': 'Link teaching staff to the subjects they teach', 'url': reverse('core:hr_subject_assignments')},
            {'icon': 'fa-file-signature', 'title': 'Contracts', 'description': 'Employment contracts, renewals and expiry tracking', 'url': reverse('core:hr_contract_list')},
            {'icon': 'fa-sitemap', 'title': 'Departments & Positions', 'description': 'Organisation structure lookups', 'url': reverse('core:hr_settings')},
        ]},
        {'title': 'Attendance', 'tiles': [
            {'icon': 'fa-clipboard-check', 'title': 'Daily Attendance', 'description': 'Mark daily employee attendance', 'url': reverse('core:hr_attendance_register')},
            {'icon': 'fa-list', 'title': 'Attendance Records', 'description': 'Browse and filter marked attendance', 'url': reverse('core:hr_attendance_records')},
            {'icon': 'fa-chart-bar', 'title': 'Attendance Report', 'description': 'Department-wide attendance report', 'url': reverse('core:hr_attendance_report')},
        ]},
        {'title': 'Leave', 'tiles': [
            {'icon': 'fa-calendar-minus', 'title': 'Leave Requests', 'description': 'Review, approve and reject leave requests', 'url': reverse('core:hr_leave_list')},
            {'icon': 'fa-balance-scale', 'title': 'Leave Balances', 'description': 'Entitlement, used and remaining days by employee', 'url': reverse('core:hr_leave_balances')},
            {'icon': 'fa-file-alt', 'title': 'Leave Report', 'description': 'Printable department-wide leave balance report', 'url': reverse('core:hr_leave_balance_report')},
        ]},
        {'title': 'Payroll', 'tiles': [
            {'icon': 'fa-money-check-alt', 'title': 'Salary Structures', 'description': 'Payroll categories and payroll groups', 'url': reverse('core:hr_payroll_settings')},
            {'icon': 'fa-play-circle', 'title': 'Payroll Runs', 'description': 'Generate payslips for a group and pay period', 'url': reverse('core:hr_payroll_runs')},
            {'icon': 'fa-receipt', 'title': 'Payslips', 'description': 'View, approve, reject, regenerate and mark payslips paid', 'url': reverse('core:hr_payslip_list')},
            {'icon': 'fa-chart-line', 'title': 'Payroll Report', 'description': 'Run and save payslip report templates', 'url': reverse('core:hr_payslip_report')},
        ]},
        {'title': 'Lifecycle', 'tiles': [
            {'icon': 'fa-briefcase', 'title': 'Recruitment', 'description': 'Vacancies, applicant pipeline and convert-to-employee', 'url': reverse('core:hr_vacancy_list')},
            {'icon': 'fa-list-check', 'title': 'Onboarding', 'description': 'New-starter checklists and their progress', 'url': reverse('core:hr_onboarding_list')},
            {'icon': 'fa-chart-line', 'title': 'Performance', 'description': 'Appraisals and classroom-observation reviews', 'url': reverse('core:hr_performance_list')},
            {'icon': 'fa-graduation-cap', 'title': 'Training', 'description': 'Training records, certifications and mandatory-training gaps', 'url': reverse('core:hr_training_list')},
            {'icon': 'fa-right-from-bracket', 'title': 'Employee Exit', 'description': 'Offboarding, clearance checklists and final settlement', 'url': reverse('core:hr_exit_list')},
            {'icon': 'fa-scale-balanced', 'title': 'Employee Relations', 'description': 'Disciplinary cases and grievances (restricted)', 'url': reverse('core:hr_relations')},
        ]},
        {'title': 'Operations', 'tiles': [
            {'icon': 'fa-list-check', 'title': 'HR Tasks', 'description': 'Reminders and auto-generated HR to-dos', 'url': reverse('core:hr_task_list')},
            {'icon': 'fa-file-lines', 'title': 'Policies', 'description': 'Publish policies and track staff acknowledgement', 'url': reverse('core:hr_policy_list')},
            {'icon': 'fa-clock-rotate-left', 'title': 'Audit Trail', 'description': 'Who changed what across HR records', 'url': reverse('core:hr_audit_list')},
        ]},
        {'title': 'Reports & Settings', 'tiles': [
            {'icon': 'fa-folder-open', 'title': 'Reports', 'description': 'All HR reports in one place', 'url': reverse('core:hr_reports')},
            {'icon': 'fa-sliders-h', 'title': 'HR Settings', 'description': 'Categories, positions, departments, grades, leave types, working days', 'url': reverse('core:hr_settings')},
            {'icon': 'fa-cash-register', 'title': 'Cashier Settings', 'description': 'Configure the employee shown as Cashier on fee receipts', 'url': reverse('core:hr_cashier_settings')},
            {'icon': 'fa-cog', 'title': 'Payslip Display Settings', 'description': 'Configure what appears on a generated payslip', 'url': reverse('core:hr_payslip_settings')},
        ]},
    ]


class HRDashboardView(PermissionRequiredMixin, TemplateView):
    """HR home — headline stats plus the module's functional-domain tile groups."""
    template_name = 'core/hr/dashboard.html'
    required_permissions = HR_ANY

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['header_actions'] = [
            {'label': 'Back', 'variant': 'outline', 'icon': 'fa-arrow-left', 'url': reverse('core:dashboard')},
        ]
        context['dashboard_sections'] = _hr_dashboard_sections()

        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            try:
                from portal.hr_selectors import hr_dashboard as _hr_dashboard
                snapshot = _hr_dashboard(tenant)
                context['hr_alerts'] = snapshot.get('alerts', {})
            except Exception:
                context['hr_alerts'] = {}
            svc = EmployeeService(tenant)
            teaching = svc.get_teaching_staff().count()
            active = svc.count_active_employees()
            context['stat_cards'] = [
                {'label': 'Active Staff', 'value': active, 'icon': 'fa-users', 'variant': 'primary'},
                {'label': 'Teaching Staff', 'value': teaching, 'icon': 'fa-chalkboard-teacher', 'variant': 'primary'},
                {'label': 'Non-Teaching', 'value': max(active - teaching, 0), 'icon': 'fa-user-tie', 'variant': 'primary'},
                {'label': 'Pending Leave', 'value': EmployeeLeave.objects.filter(tenant=tenant, status='pending').count(), 'icon': 'fa-hourglass-half', 'variant': 'warning'},
                {'label': 'Payslips Awaiting Approval', 'value': Payslip.objects.filter(tenant=tenant, status='generated').count(), 'icon': 'fa-file-invoice-dollar', 'variant': 'warning'},
            ]
        return context


class HRReportsView(PermissionRequiredMixin, TemplateView):
    """Index of every HR report."""
    template_name = 'core/hr/reports.html'
    required_permissions = HR_ANY

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['back_url'] = reverse('core:hr_dashboard')
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Reports'},
        ]
        context['report_tiles'] = [
            {'icon': 'fa-chart-bar', 'title': 'Attendance Report', 'description': 'Department-wide employee attendance over a date range', 'url': reverse('core:hr_attendance_report')},
            {'icon': 'fa-balance-scale', 'title': 'Leave Balance Report', 'description': 'Entitlement, used and remaining leave by employee', 'url': reverse('core:hr_leave_balance_report')},
            {'icon': 'fa-chart-line', 'title': 'Payslip Report', 'description': 'Filterable payslip report with saved templates', 'url': reverse('core:hr_payslip_report')},
        ]
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            svc = EmployeeService(tenant)
            context['headcount'] = {
                'active': svc.count_active_employees(),
                'inactive': svc.count(status=False),
                'teaching': svc.get_teaching_staff().count(),
            }
        return context


class CashierSettingsView(PermissionRequiredMixin, TemplateView):
    """Configure the tenant-wide employee whose name prints as Cashier on
    fee receipts (core/fees/student_collection_receipt_pdf.html)."""
    template_name = 'core/hr/settings/cashier_settings.html'
    required_permission = 'hr.settings.manage'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['settings'] = FeeReceiptSettings.get_settings(tenant)
            context['employees'] = Employee.objects.filter(
                tenant=tenant, status=True,
            ).order_by('first_name', 'last_name')
        return context


@require_http_methods(["POST"])
@login_required
@require_permission('hr.settings.manage')
def cashier_settings_update_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    settings = FeeReceiptSettings.get_settings(tenant)
    settings.cashier_id = request.POST.get('cashier_employee_id') or None

    receipt_prefix = request.POST.get('receipt_prefix', '').strip()
    if receipt_prefix:
        settings.receipt_prefix = receipt_prefix[:10]

    next_receipt_number = request.POST.get('next_receipt_number', '').strip()
    if next_receipt_number:
        try:
            next_receipt_number = int(next_receipt_number)
        except ValueError:
            return JsonResponse({'error': 'Next receipt number must be a whole number'}, status=400)
        if next_receipt_number < 1:
            return JsonResponse({'error': 'Next receipt number must be at least 1'}, status=400)
        settings.next_receipt_number = next_receipt_number

    settings.save()
    return JsonResponse({'success': True})


class HRLookupListView(PermissionRequiredMixin, ListView):
    """Returns the table partial for one lookup type. Only ever loaded as an
    HTMX fragment (from a tab on HRSettingsLandingView), never as a full page.
    """
    paginate_by = 15
    context_object_name = 'items'

    required_permission = 'hr.settings.manage'

    def dispatch(self, request, *args, **kwargs):
        self.lookup_key = kwargs.get('lookup_key')
        if self.lookup_key not in LOOKUP_CONFIG:
            raise Http404('Unknown HR lookup type')
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [LOOKUP_TEMPLATES[self.lookup_key]]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        search = self.request.GET.get('search', '')
        return HRSettingsService(tenant).list(self.lookup_key, search=search)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lookup_key'] = self.lookup_key
        tenant = getattr(self.request, 'tenant', None)
        if self.lookup_key == 'position' and tenant:
            context['categories'] = HRSettingsService(tenant).list('category')
        return context


def _render_lookup_fragment(request, lookup_key):
    tenant = getattr(request, 'tenant', None)
    service = HRSettingsService(tenant)
    queryset = service.list(lookup_key, search=request.GET.get('search', ''))
    extra_context = {'lookup_key': lookup_key}
    if lookup_key == 'position':
        extra_context['categories'] = service.list('category')
    return _render_paginated_fragment(
        request, queryset, LOOKUP_TEMPLATES[lookup_key], 'items',
        paginate_by=15, extra_context=extra_context,
    )


@require_http_methods(["POST"])
@login_required
@require_permission('hr.settings.manage')
def hr_lookup_create_api(request, lookup_key):
    if lookup_key not in LOOKUP_CONFIG:
        raise Http404('Unknown HR lookup type')

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        service = HRSettingsService(tenant)
        data = _extract_fields(request, lookup_key)
        if not data.get('name'):
            return JsonResponse({'name': ['This field is required']}, status=400)
        service.create(lookup_key, user=request.user, **data)
        return HttpResponse(_render_lookup_fragment(request, lookup_key))
    except DuplicateException as e:
        return JsonResponse({'name': [str(e.message)]}, status=400)
    except ValidationException as e:
        return JsonResponse(e.details.get('validation_errors', {'error': [e.message]}), status=400)
    except ServiceException as e:
        return JsonResponse({'error': str(e.message)}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.settings.manage')
def hr_lookup_update_api(request, lookup_key, pk):
    if lookup_key not in LOOKUP_CONFIG:
        raise Http404('Unknown HR lookup type')

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        service = HRSettingsService(tenant)
        data = _extract_fields(request, lookup_key)
        if not data.get('name'):
            return JsonResponse({'name': ['This field is required']}, status=400)
        service.update(lookup_key, pk, user=request.user, **data)
        return HttpResponse(_render_lookup_fragment(request, lookup_key))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)
    except DuplicateException as e:
        return JsonResponse({'name': [str(e.message)]}, status=400)
    except ValidationException as e:
        return JsonResponse(e.details.get('validation_errors', {'error': [e.message]}), status=400)
    except ServiceException as e:
        return JsonResponse({'error': str(e.message)}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.settings.manage')
def hr_lookup_toggle_status_api(request, lookup_key, pk):
    if lookup_key not in LOOKUP_CONFIG:
        raise Http404('Unknown HR lookup type')

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        HRSettingsService(tenant).toggle_status(lookup_key, pk)
        return HttpResponse(_render_lookup_fragment(request, lookup_key))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.settings.manage')
def hr_lookup_delete_api(request, lookup_key, pk):
    if lookup_key not in LOOKUP_CONFIG:
        raise Http404('Unknown HR lookup type')

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        HRSettingsService(tenant).delete(lookup_key, pk)
        return HttpResponse(_render_lookup_fragment(request, lookup_key))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)
    except ServiceException as e:
        return JsonResponse({'error': str(e.message)}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.settings.manage')
def working_day_settings_update_api(request):

    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    working_days = [int(d) for d in request.POST.getlist('working_days')]
    daily_hours = request.POST.get('default_daily_hours') or None
    half_day_threshold = request.POST.get('half_day_hours_threshold') or None

    try:
        WorkingDaySettingsService(tenant).update_settings(
            user=request.user,
            working_days=working_days,
            default_daily_hours=daily_hours,
            half_day_hours_threshold=half_day_threshold,
        )
        return JsonResponse({'success': True})
    except ServiceException as e:
        return JsonResponse({'error': str(e.message)}, status=400)
