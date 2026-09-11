from typing import Any, Dict, Optional

from core.models import (
    EmployeeCategory,
    EmployeePosition,
    EmployeeDepartment,
    EmployeeGrade,
    LeaveType,
    EmployeeWorkingDaySettings,
)
from .exceptions import ValidationException, NotFoundException, DuplicateException
from .logging_service import ServiceLogger, logged_operation


class HRSettingsService:
    """CRUD for the simple HR lookup tables (Employee Category/Position/
    Department/Grade, Leave Type). These all share the same shape (a tenant-
    scoped name + status, plus a handful of type-specific fields), so this is
    one thin wrapper parameterized by lookup type instead of five
    near-identical service classes.
    """

    LOOKUP_MODELS = {
        'category': EmployeeCategory,
        'position': EmployeePosition,
        'department': EmployeeDepartment,
        'grade': EmployeeGrade,
        'leave_type': LeaveType,
    }

    def __init__(self, tenant):
        self.tenant = tenant
        self.logger = ServiceLogger('hr_settings', tenant)

    def _model(self, lookup_key: str):
        try:
            return self.LOOKUP_MODELS[lookup_key]
        except KeyError:
            raise ValidationException(f"Unknown HR lookup type '{lookup_key}'")

    def _get(self, model, obj_id: Any):
        try:
            return model.objects.get(tenant=self.tenant, id=obj_id)
        except (model.DoesNotExist, ValueError, TypeError):
            raise NotFoundException(
                f"{model.__name__} with id {obj_id} not found",
                details={"model": model.__name__, "id": obj_id},
            )

    def list(self, lookup_key: str, search: Optional[str] = None):
        model = self._model(lookup_key)
        queryset = model.objects.filter(tenant=self.tenant)
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by('name')

    @logged_operation(action='create', resource_type='hr_lookup', log_result=True)
    def create(self, lookup_key: str, user=None, **data: Dict[str, Any]):
        model = self._model(lookup_key)
        name = data.get('name')
        if name and model.objects.filter(tenant=self.tenant, name__iexact=name).exists():
            raise DuplicateException(
                f"{model.__name__} with name '{name}' already exists",
                details={"name": name},
            )
        try:
            instance = model(tenant=self.tenant, **data)
            instance.full_clean()
            instance.save()
        except Exception as e:
            from django.core.exceptions import ValidationError
            if isinstance(e, ValidationError):
                raise ValidationException(
                    "Object creation failed validation",
                    details={"validation_errors": e.message_dict},
                    original_exception=e,
                )
            raise
        return instance

    @logged_operation(action='update', resource_type='hr_lookup', log_result=True)
    def update(self, lookup_key: str, obj_id: Any, user=None, **data: Dict[str, Any]):
        model = self._model(lookup_key)
        instance = self._get(model, obj_id)

        name = data.get('name')
        if name and model.objects.filter(tenant=self.tenant, name__iexact=name).exclude(id=obj_id).exists():
            raise DuplicateException(
                f"{model.__name__} with name '{name}' already exists",
                details={"name": name},
            )

        for field, value in data.items():
            setattr(instance, field, value)

        try:
            instance.full_clean()
            instance.save()
        except Exception as e:
            from django.core.exceptions import ValidationError
            if isinstance(e, ValidationError):
                raise ValidationException(
                    "Object update failed validation",
                    details={"validation_errors": e.message_dict},
                    original_exception=e,
                )
            raise
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


class WorkingDaySettingsService:
    def __init__(self, tenant):
        self.tenant = tenant
        self.logger = ServiceLogger('hr_settings', tenant)

    def get_settings(self) -> EmployeeWorkingDaySettings:
        return EmployeeWorkingDaySettings.get_settings(self.tenant)

    @logged_operation(action='update', resource_type='employee_working_day_settings')
    def update_settings(self, user=None, **data: Dict[str, Any]) -> EmployeeWorkingDaySettings:
        settings = self.get_settings()
        for field, value in data.items():
            setattr(settings, field, value)
        settings.save()
        return settings
