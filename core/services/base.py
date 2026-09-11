from abc import ABC
from typing import Any, Dict, Optional, Type, TypeVar, Generic
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from .exceptions import (
    ServiceException,
    ValidationException,
    NotFoundException,
    TenantException,
    handle_service_exceptions
)

T = TypeVar('T', bound=models.Model)


class BaseService(Generic[T], ABC):
    def __init__(self, model_class: Type[T], tenant: Optional[models.Model] = None):
        self.model_class = model_class
        self.tenant = tenant
        self._validate_initialization()
    
    def _validate_initialization(self) -> None:
        if self.model_class is not None and not issubclass(self.model_class, models.Model):
            raise ServiceException("model_class must be a Django Model subclass")
    
    def get_tenant(self) -> Optional[models.Model]:
        return self.tenant
    
    def set_tenant(self, tenant: models.Model) -> None:
        self.tenant = tenant
    
    @handle_service_exceptions
    def get_base_queryset(self) -> QuerySet[T]:
        if self.model_class is None:
            raise ServiceException("Cannot get queryset for service without model_class")
        
        queryset = self.model_class.objects.all()
        
        if (hasattr(self.model_class, 'tenant') and 
            self.tenant is not None and 
            hasattr(self.tenant, 'id')):
            queryset = queryset.filter(tenant=self.tenant)
        
        return queryset
    
    @handle_service_exceptions
    def get_by_id(self, obj_id: Any) -> T:
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            return self.get_base_queryset().get(id=obj_id)
        except (self.model_class.DoesNotExist, DjangoValidationError, ValueError, TypeError):
            # A malformed id (e.g. not a valid UUID) is treated as "not found"
            # rather than leaking a database/validation error.
            raise NotFoundException(
                f"{self.model_class.__name__} with id {obj_id} not found",
                details={"model": self.model_class.__name__, "id": obj_id}
            )
    
    @handle_service_exceptions
    def exists(self, **filters) -> bool:
        return self.get_base_queryset().filter(**filters).exists()
    
    @handle_service_exceptions
    def get_or_none(self, **filters) -> Optional[T]:
        try:
            return self.get_base_queryset().get(**filters)
        except self.model_class.DoesNotExist:
            return None
    
    @handle_service_exceptions
    def filter(self, **filters) -> QuerySet[T]:
        return self.get_base_queryset().filter(**filters)
    
    @handle_service_exceptions
    def count(self, **filters) -> int:
        return self.filter(**filters).count()
    
    @handle_service_exceptions
    @transaction.atomic
    def create(self, **data) -> T:
        if (hasattr(self.model_class, 'tenant') and 
            'tenant' not in data and 
            self.tenant is not None):
            data['tenant'] = self.tenant

        self._validate_create_data(data)
        
        try:
            instance = self.model_class(**data)
            instance.full_clean()
            instance.save()
            return instance
        except ValidationError as e:
            raise ValidationException(
                "Object creation failed validation",
                details={"validation_errors": e.message_dict},
                original_exception=e
            )
    
    @handle_service_exceptions
    @transaction.atomic
    def update(self, obj_id: Any, **data) -> T:
        instance = self.get_by_id(obj_id)
        
        self._validate_update_data(instance, data)
        
        for field, value in data.items():
            if hasattr(instance, field):
                setattr(instance, field, value)
        
        try:
            instance.full_clean()
            instance.save()
            return instance
        except ValidationError as e:
            raise ValidationException(
                "Object update failed validation",
                details={"validation_errors": e.message_dict},
                original_exception=e
            )
    
    @handle_service_exceptions
    @transaction.atomic
    def delete(self, obj_id: Any, soft_delete: bool = True) -> bool:
        instance = self.get_by_id(obj_id)
        
        if soft_delete and hasattr(instance, 'is_deleted'):
            instance.is_deleted = True
            instance.save()
        else:
            instance.delete()
        
        return True
    
    @handle_service_exceptions
    @transaction.atomic
    def bulk_create(self, objects_data: list) -> list[T]:
        instances = []
        for data in objects_data:
            if (hasattr(self.model_class, 'tenant') and 
                'tenant' not in data and 
                self.tenant is not None):
                data['tenant'] = self.tenant
            
            instances.append(self.model_class(**data))
        
        for instance in instances:
            instance.full_clean()
        
        return self.model_class.objects.bulk_create(instances)
    
    def _validate_create_data(self, data: Dict[str, Any]) -> None:
        pass
    
    def _validate_update_data(self, instance: T, data: Dict[str, Any]) -> None:
        pass
    
    def _ensure_tenant_access(self, instance: T) -> None:
        if (hasattr(instance, 'school') and 
            self.tenant is not None and 
            instance.school != self.tenant):
            raise TenantException(
                f"Access denied: {self.model_class.__name__} belongs to different tenant",
                details={
                    "model": self.model_class.__name__,
                    "instance_tenant": instance.school.id if instance.school else None,
                    "current_tenant": self.tenant.id if self.tenant else None
                }
            )


class TenantAwareService(BaseService[T]):
    def __init__(self, model_class: Type[T], tenant: models.Model):
        if tenant is None:
            raise TenantException("TenantAwareService requires a tenant context")
        super().__init__(model_class, tenant)
    
    def set_tenant(self, tenant: models.Model) -> None:
        if tenant is None:
            raise TenantException("Tenant cannot be None for TenantAwareService")
        super().set_tenant(tenant)