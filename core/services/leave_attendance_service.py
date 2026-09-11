from datetime import date
from typing import Any, Dict, List, Optional

from django.db.models import Q
from django.utils import timezone

from core.models import Employee, EmployeeLeave, EmployeeAttendance, LeaveType, EmployeeDepartment
from .base import TenantAwareService
from .exceptions import ValidationException, NotFoundException, BusinessLogicException
from .logging_service import ServiceLogger, logged_operation


class LeaveService(TenantAwareService[EmployeeLeave]):
    def __init__(self, tenant):
        super().__init__(EmployeeLeave, tenant)
        self.logger = ServiceLogger('leave', tenant)

    @logged_operation(action='request', resource_type='employee_leave', log_result=True)
    def request_leave(
        self,
        employee_id: str,
        leave_type_id: str,
        start_date: date,
        end_date: date,
        reason: str,
        user=None,
    ) -> EmployeeLeave:
        if end_date < start_date:
            raise ValidationException("End date cannot be before start date")

        employee = self._get_employee(employee_id)
        leave_type = self._get_leave_type(leave_type_id) if leave_type_id else None

        return self.create(
            employee=employee,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status='pending',
        )

    @logged_operation(action='approve', resource_type='employee_leave', log_result=True)
    def approve_leave(self, leave_id: str, approver: Employee, remark: str = None) -> EmployeeLeave:
        leave = self.get_by_id(leave_id)
        leave.status = 'approved'
        leave.is_approved = True
        leave.approved_by = approver
        if remark:
            leave.manager_remark = remark
        leave.save()
        return leave

    @logged_operation(action='reject', resource_type='employee_leave', log_result=True)
    def reject_leave(self, leave_id: str, approver: Employee, remark: str = None) -> EmployeeLeave:
        leave = self.get_by_id(leave_id)
        leave.status = 'rejected'
        leave.is_approved = False
        leave.approved_by = approver
        if remark:
            leave.manager_remark = remark
        leave.save()
        return leave

    # ── two-step workflow: employee -> supervisor -> HR ─────────────────
    @logged_operation(action='supervisor_review', resource_type='employee_leave', log_result=True)
    def supervisor_review(
        self, leave_id: str, reviewer: Employee, approve: bool, remark: str = None
    ) -> EmployeeLeave:
        leave = self.get_by_id(leave_id)
        leave.supervisor_status = 'approved' if approve else 'rejected'
        leave.supervisor_by = reviewer
        leave.supervisor_remark = remark or ''
        leave.supervisor_acted_at = timezone.now()
        if not approve:
            leave.status = 'rejected'
            leave.is_approved = False
        self._sync_overall(leave)
        leave.save()
        return leave

    @logged_operation(action='hr_review', resource_type='employee_leave', log_result=True)
    def hr_review(
        self, leave_id: str, reviewer: Employee, approve: bool, remark: str = None
    ) -> EmployeeLeave:
        leave = self.get_by_id(leave_id)
        if leave.supervisor_status != 'approved':
            raise BusinessLogicException(
                "Leave must be approved by the supervisor before HR review."
            )
        leave.hr_status = 'approved' if approve else 'rejected'
        leave.hr_by = reviewer
        leave.hr_remark = remark or ''
        leave.hr_acted_at = timezone.now()
        self._sync_overall(leave)
        leave.save()
        return leave

    @staticmethod
    def _sync_overall(leave: EmployeeLeave) -> None:
        """Collapse the two step results into the legacy ``status`` /
        ``is_approved`` fields the rest of the app still reads."""
        if 'rejected' in (leave.supervisor_status, leave.hr_status):
            leave.status, leave.is_approved = 'rejected', False
        elif leave.supervisor_status == 'approved' and leave.hr_status == 'approved':
            leave.status, leave.is_approved = 'approved', True
            leave.approved_by = leave.hr_by or leave.supervisor_by
        else:
            leave.status, leave.is_approved = 'pending', False

    def leave_calendar(
        self, start: date, end: date, department_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Approved leave overlapping [start, end], one row per leave, for the
        HR leave calendar."""
        qs = EmployeeLeave.objects.filter(
            tenant=self.tenant,
            status='approved',
            start_date__lte=end,
            end_date__gte=start,
        ).select_related('employee', 'employee__employee_department', 'leave_type')
        if department_id:
            qs = qs.filter(employee__employee_department_id=department_id)
        rows = []
        for leave in qs.order_by('start_date'):
            rows.append({
                'id': str(leave.id),
                'employee_id': str(leave.employee_id),
                'employee_name': leave.employee.full_name,
                'department': getattr(leave.employee.employee_department, 'name', None),
                'leave_type': getattr(leave.leave_type, 'name', leave.leave_type_legacy or 'Leave'),
                'start_date': leave.start_date,
                'end_date': leave.end_date,
            })
        return rows

    def _get_employee(self, employee_id: str) -> Employee:
        try:
            return Employee.objects.get(id=employee_id, tenant=self.tenant)
        except Employee.DoesNotExist:
            raise NotFoundException(f"Employee with id {employee_id} not found")

    def _get_leave_type(self, leave_type_id: str) -> LeaveType:
        try:
            return LeaveType.objects.get(id=leave_type_id, tenant=self.tenant)
        except LeaveType.DoesNotExist:
            raise NotFoundException(f"Leave type with id {leave_type_id} not found")

    def get_leave_balance(self, employee: Employee, leave_type: LeaveType, year: int) -> Dict[str, Any]:
        used = 0
        approved_leaves = EmployeeLeave.objects.filter(
            tenant=self.tenant,
            employee=employee,
            leave_type=leave_type,
            status='approved',
            start_date__year=year,
        )
        for leave in approved_leaves:
            used += (leave.end_date - leave.start_date).days + 1

        allocated = leave_type.default_annual_days
        return {
            'leave_type': leave_type,
            'allocated': allocated,
            'used': used,
            'remaining': max(allocated - used, 0),
        }

    def get_department_leave_balance_report(self, department_id: Optional[str] = None, year: Optional[int] = None) -> List[Dict[str, Any]]:
        year = year or date.today().year
        employees = Employee.objects.filter(tenant=self.tenant, status=True).select_related('employee_department')
        if department_id:
            employees = employees.filter(employee_department_id=department_id)
        employees = employees.order_by('employee_department__name', 'first_name', 'last_name')

        leave_types = list(LeaveType.objects.filter(tenant=self.tenant, status=True))

        rows = []
        for employee in employees:
            balances = [self.get_leave_balance(employee, lt, year) for lt in leave_types]
            rows.append({
                'employee': employee,
                'department': employee.employee_department,
                'balances': balances,
            })
        return rows


class AttendanceService(TenantAwareService[EmployeeAttendance]):
    """Employee attendance tracking — deliberately separate from any
    student-attendance service; different domain, different model.
    """

    def __init__(self, tenant):
        super().__init__(EmployeeAttendance, tenant)
        self.logger = ServiceLogger('employee_attendance', tenant)

    def _is_holiday(self, target_date: date) -> bool:
        from core.models import Event
        return Event.objects.filter(
            tenant=self.tenant,
            is_holiday=True,
            start_date__date__lte=target_date,
            end_date__date__gte=target_date,
        ).exists()

    def _default_status_for_date(self, target_date: date) -> str:
        from core.models import EmployeeWorkingDaySettings
        settings = EmployeeWorkingDaySettings.get_settings(self.tenant)
        if target_date.weekday() not in settings.working_days or self._is_holiday(target_date):
            return 'holiday'
        return 'present'

    @logged_operation(action='mark', resource_type='employee_attendance', log_result=True)
    def mark_attendance(self, employee_id: str, target_date: date, status: str, marked_by: Employee = None, remarks: str = None) -> EmployeeAttendance:
        employee = Employee.objects.get(id=employee_id, tenant=self.tenant)
        attendance, _ = EmployeeAttendance.objects.update_or_create(
            tenant=self.tenant, employee=employee, date=target_date,
            defaults={'status': status, 'marked_by': marked_by, 'remarks': remarks or ''},
        )
        return attendance

    @logged_operation(action='bulk_mark', resource_type='employee_attendance')
    def bulk_mark_attendance(self, employee_ids: List[str], target_date: date, status: str, marked_by: Employee = None) -> int:
        count = 0
        for employee_id in employee_ids:
            self.mark_attendance(employee_id, target_date, status, marked_by=marked_by)
            count += 1
        return count

    def get_department_attendance_report(self, start_date: date, end_date: date, department_id: Optional[str] = None) -> List[Dict[str, Any]]:
        employees = Employee.objects.filter(tenant=self.tenant, status=True).select_related('employee_department')
        if department_id:
            employees = employees.filter(employee_department_id=department_id)
        employees = employees.order_by('employee_department__name', 'first_name', 'last_name')

        rows = []
        for employee in employees:
            records = EmployeeAttendance.objects.filter(
                tenant=self.tenant, employee=employee, date__gte=start_date, date__lte=end_date,
            )
            present = records.filter(status='present').count()
            absent = records.filter(status='absent').count()
            on_leave = records.filter(status='on_leave').count()
            half_day = records.filter(status='half_day').count()
            marked_total = records.exclude(status='holiday').count()
            percentage = round((present / marked_total) * 100, 1) if marked_total else None

            rows.append({
                'employee': employee,
                'department': employee.employee_department,
                'present': present,
                'absent': absent,
                'on_leave': on_leave,
                'half_day': half_day,
                'percentage': percentage,
            })
        return rows
