from typing import Dict, Any, List, Optional
from datetime import date, datetime
from django.db import transaction
from django.db.models import Q, QuerySet, Count

from core.models import (
    Employee, EmployeeCategory, EmployeeDepartment, EmployeePosition, EmployeeGrade,
    EmploymentHistoryEvent,
)
from .base import TenantAwareService
from .hr_audit import record_hr_audit
from .exceptions import (
    ValidationException,
    NotFoundException,
    DuplicateException,
    BusinessLogicException
)
from .logging_service import ServiceLogger, logged_operation


def _label(value: Any) -> Optional[str]:
    """Readable string for an FK id / enum value stored in a history event."""
    if value is None:
        return None
    for model in (EmployeePosition, EmployeeDepartment, EmployeeGrade, Employee):
        try:
            return str(model.objects.filter(pk=value).first() or value)
        except Exception:
            continue
    return str(value)


class EmployeeService(TenantAwareService[Employee]):
    def __init__(self, tenant):
        super().__init__(Employee, tenant)
        self.logger = ServiceLogger('employee', tenant)
    
    @logged_operation(action='create', resource_type='employee', log_result=True)
    def create_employee(
        self,
        employee_number: str,
        first_name: str,
        last_name: str,
        joining_date: date,
        gender: bool,
        middle_name: str = None,
        job_title: str = None,
        email: str = None,
        mobile_phone: str = None,
        user=None,
        **additional_data
    ) -> Employee:
        """Create a new employee with validation"""
        if self.exists(employee_number=employee_number):
            raise DuplicateException(
                f"Employee with number '{employee_number}' already exists",
                details={"employee_number": employee_number}
            )
        
        employee_data = {
            "employee_number": employee_number,
            "first_name": first_name,
            "last_name": last_name,
            "middle_name": middle_name,
            "joining_date": joining_date,
            "gender": gender,
            "job_title": job_title,
            "email": email,
            "mobile_phone": mobile_phone,
            "user": user,
            "tenant": self.tenant,
            **additional_data
        }

        employee = self.create(**employee_data)

        # Every new hire gets an onboarding checklist. Never let this break the
        # create — it can always be (re)generated when the tab is opened.
        try:
            from .hr_onboarding_service import OnboardingService
            OnboardingService(self.tenant).ensure_for_employee(employee)
        except Exception:  # pragma: no cover - onboarding is non-critical here
            import logging
            logging.getLogger(__name__).exception(
                "Failed to auto-create onboarding checklist for %s", employee.id
            )

        return employee
    
    # Field -> (EmploymentHistoryEvent.event_type) for changes worth recording
    # on the employee's Employment History tab.
    TRACKED_FIELDS = {
        "employee_position_id": "position_change",
        "employee_department_id": "department_change",
        "employee_grade_id": "grade_change",
        "reporting_manager_id": "manager_change",
        "employment_status": "status_change",
        "job_title": "position_change",
    }

    @logged_operation(action='update', resource_type='employee')
    def update_employee(self, employee_id: Any, actor=None, **update_data) -> Employee:
        """Update employee information.

        Changes to :attr:`TRACKED_FIELDS` are recorded as
        :class:`EmploymentHistoryEvent` rows and written to the HR audit trail.
        """
        employee = self.get_by_id(employee_id)

        # Validate employee number uniqueness if being changed
        if 'employee_number' in update_data:
            new_number = update_data['employee_number']
            if (new_number != employee.employee_number and
                self.exists(employee_number=new_number)):
                raise DuplicateException(
                    f"Employee number '{new_number}' already exists",
                    details={"employee_number": new_number}
                )

        before = {f: getattr(employee, f, None) for f in self.TRACKED_FIELDS}
        updated = self.update(employee_id, **update_data)
        self._record_changes(updated, before, actor)
        return updated

    def _record_changes(self, employee: Employee, before: dict, actor) -> None:
        today = date.today()
        for field, event_type in self.TRACKED_FIELDS.items():
            old = before.get(field)
            new = getattr(employee, field, None)
            if old == new:
                continue
            EmploymentHistoryEvent.objects.create(
                tenant=self.tenant,
                employee=employee,
                event_type=event_type,
                effective_date=today,
                old_value={field: _label(old)},
                new_value={field: _label(new)},
                created_by_id=getattr(actor, "id", None),
            )
            record_hr_audit(
                self.tenant, actor=actor, action="employee.update",
                target_type="employee", target_id=employee.id,
                field=field, old_value=_label(old), new_value=_label(new),
            )
    
    def get_active_employees(self) -> QuerySet[Employee]:
        """Get all active employees"""
        return self.filter(status=True)
    
    def get_inactive_employees(self) -> QuerySet[Employee]:
        """Get all inactive employees"""
        return self.filter(status=False)

    def get_teaching_staff(self, active_only: bool = True) -> QuerySet[Employee]:
        """Get employees flagged as teaching staff"""
        queryset = self.get_active_employees() if active_only else self.get_base_queryset()
        return queryset.filter(is_teaching_staff=True)

    def search_employees(
        self,
        query: str = None,
        department_id: str = None,
        category_id: str = None,
        position_id: str = None,
        grade_id: str = None,
        employment_status: str = None,
        contract_type: str = None,
        joined_from: date = None,
        joined_to: date = None,
        active_only: bool = True,
        staff_type: str = 'all'
    ) -> QuerySet[Employee]:
        """Search employees with various filters.

        staff_type: 'teaching', 'non_teaching', or 'all' (default) — this is
        the Employees page's general-purpose search, covering every category
        of staff, not just teachers.
        """
        queryset = self.get_active_employees() if active_only else self.get_base_queryset()

        if staff_type == 'teaching':
            queryset = queryset.filter(is_teaching_staff=True)
        elif staff_type == 'non_teaching':
            queryset = queryset.filter(is_teaching_staff=False)

        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(middle_name__icontains=query) |
                Q(employee_number__icontains=query) |
                Q(email__icontains=query)
            )

        if department_id:
            queryset = queryset.filter(employee_department_id=department_id)

        if category_id:
            queryset = queryset.filter(employee_category_id=category_id)

        if position_id:
            queryset = queryset.filter(employee_position_id=position_id)

        if grade_id:
            queryset = queryset.filter(employee_grade_id=grade_id)

        if employment_status:
            queryset = queryset.filter(employment_status=employment_status)

        if contract_type:
            queryset = queryset.filter(contracts__contract_type=contract_type).distinct()

        if joined_from:
            queryset = queryset.filter(joining_date__gte=joined_from)

        if joined_to:
            queryset = queryset.filter(joining_date__lte=joined_to)

        return queryset.order_by('first_name', 'last_name')
    
    def get_by_employee_number(self, employee_number: str) -> Employee:
        """Get employee by employee number"""
        employee = self.get_or_none(employee_number=employee_number)
        if not employee:
            raise NotFoundException(
                f"Employee with number '{employee_number}' not found",
                details={"employee_number": employee_number}
            )
        return employee
    
    def count_active_employees(self) -> int:
        """Count active employees"""
        return self.count(status=True)
    
    def count_employees_by_department(self) -> Dict[str, int]:
        """Get employee count by department"""
        return dict(
            self.get_active_employees()
            .values_list('employee_department__name')
            .annotate(count=Count('id'))
            .values_list('employee_department__name', 'count')
        )
    
    def get_employees_by_department(self, department_id: str) -> QuerySet[Employee]:
        """Get employees in a specific department"""
        return self.get_active_employees().filter(employee_department_id=department_id)
    
    def get_employees_by_manager(self, manager_id: str) -> QuerySet[Employee]:
        """Get employees reporting to a manager"""
        return self.get_active_employees().filter(reporting_manager_id=manager_id)
    
    @logged_operation(action='deactivate', resource_type='employee')
    def deactivate_employee(
        self, 
        employee_id: Any, 
        reason: str = None,
        effective_date: date = None
    ) -> Employee:
        """Deactivate an employee"""
        employee = self.get_by_id(employee_id)
        
        if not employee.status:
            raise BusinessLogicException(
                "Employee is already inactive",
                details={"employee_id": employee_id}
            )
        
        update_data = {
            "status": False
        }
        
        if effective_date:
            update_data["last_working_date"] = effective_date
            
        return self.update(employee_id, **update_data)
    
    @logged_operation(action='activate', resource_type='employee')
    def activate_employee(self, employee_id: Any) -> Employee:
        """Reactivate an employee"""
        employee = self.get_by_id(employee_id)
        
        if employee.status:
            raise BusinessLogicException(
                "Employee is already active",
                details={"employee_id": employee_id}
            )
        
        return self.update(employee_id, status=True)
    
    def get_employee_stats(self) -> Dict[str, Any]:
        """Get employee statistics"""
        return {
            "total_active": self.count_active_employees(),
            "total_inactive": self.count(status=False),
            "by_department": self.count_employees_by_department(),
            "recent_joinings": self.get_active_employees()
                .order_by('-joining_date')[:10]
                .values('first_name', 'last_name', 'employee_number', 'joining_date')
        }