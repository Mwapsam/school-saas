"""Employee leave requests, attendance marking, and the two department-wide
reports (attendance, leave balance).
"""
from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, TemplateView, View

from core.models import Employee, EmployeeLeave, LeaveType, EmployeeDepartment, EmployeeAttendance
from core.services.leave_attendance_service import LeaveService, AttendanceService
from core.services.exceptions import ServiceException, ValidationException, NotFoundException
from core.views import _render_paginated_fragment
from core.authz.mixins import PermissionRequiredMixin, require_permission


def _acting_employee(request, tenant):
    """Best-effort: the Employee record linked to the logged-in admin's own
    login, used to attribute leave approvals/rejections. None if the admin
    has no linked Employee record (e.g. a pure system admin account).
    """
    return Employee.objects.filter(tenant=tenant, user=request.user).first()


def _filtered_leaves(request, tenant):
    qs = EmployeeLeave.objects.filter(tenant=tenant).select_related('employee', 'leave_type', 'approved_by')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    department_id = request.GET.get('department', '')
    if department_id:
        qs = qs.filter(employee__employee_department_id=department_id)
    return qs.order_by('-created_at')


def _render_leave_list_fragment(request, tenant):
    return _render_paginated_fragment(
        request, _filtered_leaves(request, tenant), 'core/htmx/hr/leave_list_content.html', 'leaves', paginate_by=15,
    )


class EmployeeLeaveListView(PermissionRequiredMixin, ListView):
    required_permission = 'hr.leave.view'
    template_name = 'core/hr/leave/leave_list.html'
    htmx_template_name = 'core/htmx/hr/leave_list_content.html'
    context_object_name = 'leaves'
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get('HX-Request') == 'true'
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        if self.is_htmx:
            return [self.htmx_template_name]
        return [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return []
        return _filtered_leaves(self.request, tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            context['leave_types'] = LeaveType.objects.filter(tenant=tenant, status=True)
            context['departments'] = EmployeeDepartment.objects.filter(tenant=tenant, status=True)
            context['employees'] = Employee.objects.filter(tenant=tenant, status=True).order_by('first_name')
        context['back_url'] = self.request.GET.get('back', reverse('core:hr_dashboard'))
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Leave List'},
        ]
        return context


@require_http_methods(["POST"])
@login_required
@require_permission('hr.leave.manage')
def leave_request_create_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        start = datetime.strptime(request.POST.get('start_date', ''), '%Y-%m-%d').date()
        end = datetime.strptime(request.POST.get('end_date', ''), '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Valid start and end dates are required'}, status=400)

    try:
        LeaveService(tenant).request_leave(
            employee_id=request.POST.get('employee_id'),
            leave_type_id=request.POST.get('leave_type_id') or None,
            start_date=start,
            end_date=end,
            reason=request.POST.get('reason', ''),
            user=request.user,
        )
        return HttpResponse(_render_leave_list_fragment(request, tenant))
    except (ValidationException, NotFoundException) as e:
        return JsonResponse({'error': str(e.message)}, status=400)
    except ServiceException as e:
        return JsonResponse({'error': str(e.message)}, status=400)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.leave.approve')
def leave_approve_api(request, leave_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        LeaveService(tenant).approve_leave(
            leave_id, _acting_employee(request, tenant), remark=request.POST.get('remark'),
        )
        return HttpResponse(_render_leave_list_fragment(request, tenant))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


@require_http_methods(["POST"])
@login_required
@require_permission('hr.leave.approve')
def leave_reject_api(request, leave_id):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        LeaveService(tenant).reject_leave(
            leave_id, _acting_employee(request, tenant), remark=request.POST.get('remark'),
        )
        return HttpResponse(_render_leave_list_fragment(request, tenant))
    except NotFoundException as e:
        return JsonResponse({'error': str(e.message)}, status=404)


def _filtered_attendance(request, tenant):
    qs = EmployeeAttendance.objects.filter(tenant=tenant).select_related(
        'employee', 'employee__employee_department', 'marked_by'
    )
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    department_id = request.GET.get('department', '')
    if department_id:
        qs = qs.filter(employee__employee_department_id=department_id)
    employee_id = request.GET.get('employee', '')
    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    start, end = _parse_report_range(request)
    qs = qs.filter(date__gte=start, date__lte=end)
    return qs.order_by('-date', 'employee__first_name')


class EmployeeAttendanceRecordsView(PermissionRequiredMixin, ListView):
    """Browse/filter marked employee attendance (htmx list)."""
    required_permission = 'hr.attendance.manage'
    template_name = 'core/hr/leave/attendance_records.html'
    htmx_template_name = 'core/htmx/hr/attendance_records_content.html'
    context_object_name = 'records'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        self.is_htmx = request.headers.get('HX-Request') == 'true'
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.htmx_template_name] if self.is_htmx else [self.template_name]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return EmployeeAttendance.objects.none()
        return _filtered_attendance(self.request, tenant)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        start, end = _parse_report_range(self.request)
        context['start_date'] = start
        context['end_date'] = end
        context['status_choices'] = EmployeeAttendance.STATUS_CHOICES
        if tenant:
            context['departments'] = EmployeeDepartment.objects.filter(tenant=tenant, status=True)
            context['employees'] = Employee.objects.filter(tenant=tenant, status=True).order_by('first_name')
        context['back_url'] = reverse('core:hr_dashboard')
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Attendance Records'},
        ]
        return context


class LeaveBalancesView(PermissionRequiredMixin, TemplateView):
    """Interactive leave-balance screen (the printable version stays at
    hr_leave_balance_report)."""
    required_permission = 'hr.leave.view'
    template_name = 'core/hr/leave/leave_balances.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        year = int(self.request.GET.get('year') or date.today().year)
        department_id = self.request.GET.get('department', '') or None
        context['year'] = year
        context['year_choices'] = list(range(date.today().year - 3, date.today().year + 2))
        context['department_id'] = department_id
        if tenant:
            context['departments'] = EmployeeDepartment.objects.filter(tenant=tenant, status=True)
            context['rows'] = LeaveService(tenant).get_department_leave_balance_report(department_id, year)
        context['back_url'] = reverse('core:hr_dashboard')
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Leave Balances'},
        ]
        return context


class EmployeeAttendanceRegisterView(PermissionRequiredMixin, TemplateView):
    required_permission = 'hr.attendance.manage'
    template_name = 'core/hr/leave/attendance_register.html'



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        target_date_str = self.request.GET.get('date', '')
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date() if target_date_str else date.today()
        except ValueError:
            target_date = date.today()
        context['target_date'] = target_date

        if tenant:
            employees = Employee.objects.filter(tenant=tenant, status=True).select_related(
                'employee_department'
            ).order_by('employee_department__name', 'first_name', 'last_name')
            existing = {
                a.employee_id: a for a in
                EmployeeAttendance.objects.filter(tenant=tenant, date=target_date)
            }
            context['rows'] = [
                {'employee': emp, 'attendance': existing.get(emp.id)} for emp in employees
            ]
        context['back_url'] = self.request.GET.get('back', reverse('core:hr_dashboard'))
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Attendance Register'},
        ]
        return context


@require_http_methods(["POST"])
@login_required
@require_permission('hr.attendance.manage')
def employee_attendance_mark_api(request):
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Tenant not found'}, status=400)

    try:
        target_date = datetime.strptime(request.POST.get('date', ''), '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'A valid date is required'}, status=400)

    try:
        marked_by = _acting_employee(request, tenant)
        service = AttendanceService(tenant)
        employee_ids = request.POST.getlist('employee_id')
        marked = 0
        for employee_id in employee_ids:
            status = request.POST.get(f'status_{employee_id}')
            if status:
                service.mark_attendance(employee_id, target_date, status, marked_by=marked_by)
                marked += 1
        return JsonResponse({'success': True, 'marked': marked})
    except ServiceException as e:
        return JsonResponse({'error': str(e.message)}, status=400)


def _parse_report_range(request):
    today = date.today()
    start_str = request.GET.get('start_date', '')
    end_str = request.GET.get('end_date', '')
    try:
        start = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else today.replace(day=1)
    except ValueError:
        start = today.replace(day=1)
    try:
        end = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else today
    except ValueError:
        end = today
    return start, end


class DepartmentAttendanceReportView(PermissionRequiredMixin, TemplateView):
    required_permission = 'hr.leave.view'
    template_name = 'core/hr/leave/attendance_report.html'



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        start, end = _parse_report_range(self.request)
        department_id = self.request.GET.get('department', '') or None

        context['start_date'] = start
        context['end_date'] = end
        context['department_id'] = department_id
        if tenant:
            context['departments'] = EmployeeDepartment.objects.filter(tenant=tenant, status=True)
            context['rows'] = AttendanceService(tenant).get_department_attendance_report(start, end, department_id)
        context['back_url'] = self.request.GET.get('back', reverse('core:hr_dashboard'))
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Attendance Report'},
        ]
        return context


class DepartmentAttendanceReportPDFView(PermissionRequiredMixin, View):
    required_permission = 'hr.leave.view'
    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            raise Http404('School not found')

        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        start, end = _parse_report_range(request)
        department_id = request.GET.get('department', '') or None
        rows = AttendanceService(tenant).get_department_attendance_report(start, end, department_id)

        html_content = render_to_string('core/hr/leave/attendance_report_pdf.html', {
            'school': tenant, 'start_date': start, 'end_date': end, 'rows': rows,
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="attendance_report.pdf"'
        return response


class LeaveBalanceReportView(PermissionRequiredMixin, TemplateView):
    required_permission = 'hr.leave.view'
    template_name = 'core/hr/leave/leave_balance_report.html'



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        year = int(self.request.GET.get('year') or date.today().year)
        department_id = self.request.GET.get('department', '') or None
        context['year'] = year
        context['department_id'] = department_id
        if tenant:
            context['departments'] = EmployeeDepartment.objects.filter(tenant=tenant, status=True)
            context['rows'] = LeaveService(tenant).get_department_leave_balance_report(department_id, year)
        context['back_url'] = self.request.GET.get('back', reverse('core:hr_dashboard'))
        context['crumbs'] = [
            {'label': 'HR', 'url': reverse('core:hr_dashboard')},
            {'label': 'Leave Balance Report'},
        ]
        return context


class LeaveBalanceReportPDFView(PermissionRequiredMixin, View):
    required_permission = 'hr.leave.view'
    def get(self, request):
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            raise Http404('School not found')

        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        year = int(request.GET.get('year') or date.today().year)
        department_id = request.GET.get('department', '') or None
        rows = LeaveService(tenant).get_department_leave_balance_report(department_id, year)

        html_content = render_to_string('core/hr/leave/leave_balance_report_pdf.html', {
            'school': tenant, 'year': year, 'rows': rows,
        })
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="leave_balance_report.pdf"'
        return response
