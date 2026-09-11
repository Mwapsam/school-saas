"""
Base serializer classes that integrate with services
"""
from typing import Any, Dict, Type
from rest_framework import serializers
from django.db import models

from core.services.exceptions import (
    ServiceException,
    ValidationException,
    NotFoundException,
    DuplicateException,
    TenantException
)


class ServiceSerializerMixin:
    """
    Mixin that provides service integration for DRF serializers
    Handles service exceptions and provides service context
    """
    service_class = None
    
    def get_service(self):
        """Get service instance with proper tenant context"""
        if not self.service_class:
            raise NotImplementedError("service_class must be defined")
        
        tenant = self.context.get('tenant')
        if not tenant:
            raise TenantException("Tenant context required for service operations")
        
        return self.service_class(tenant)
    
    def handle_service_exception(self, exc: ServiceException):
        """Convert service exceptions to serializer validation errors"""
        if isinstance(exc, ValidationException):
            if hasattr(exc, 'details') and exc.details:
                # Handle field-specific validation errors
                if 'field' in exc.details:
                    field_name = exc.details['field']
                    raise serializers.ValidationError({field_name: str(exc)})
                elif 'validation_errors' in exc.details:
                    # Handle Django model validation errors
                    raise serializers.ValidationError(exc.details['validation_errors'])
            
            raise serializers.ValidationError(str(exc))
        
        elif isinstance(exc, DuplicateException):
            # Handle duplicate errors as non-field errors
            raise serializers.ValidationError({'non_field_errors': [str(exc)]})
        
        elif isinstance(exc, NotFoundException):
            # Handle not found errors
            raise serializers.ValidationError({'non_field_errors': [str(exc)]})
        
        elif isinstance(exc, TenantException):
            # Handle tenant access errors
            raise serializers.ValidationError({'non_field_errors': [str(exc)]})
        
        else:
            # Generic service exception
            raise serializers.ValidationError({'non_field_errors': [str(exc)]})
    
    def create(self, validated_data):
        """Create instance using service"""
        try:
            service = self.get_service()
            return self._service_create(service, validated_data)
        except ServiceException as e:
            self.handle_service_exception(e)
    
    def update(self, instance, validated_data):
        """Update instance using service"""
        try:
            service = self.get_service()
            return self._service_update(service, instance, validated_data)
        except ServiceException as e:
            self.handle_service_exception(e)
    
    def _service_create(self, service, validated_data):
        """Override in subclasses to define service creation logic"""
        raise NotImplementedError("_service_create must be implemented")
    
    def _service_update(self, service, instance, validated_data):
        """Override in subclasses to define service update logic"""
        raise NotImplementedError("_service_update must be implemented")


class BaseServiceSerializer(ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Base serializer that combines ServiceSerializerMixin with ModelSerializer
    """
    
    class Meta:
        abstract = True
    
    def validate(self, attrs):
        """Perform custom validation using service if needed"""
        attrs = super().validate(attrs)
        
        # Allow subclasses to add service-based validation
        if hasattr(self, 'service_validate'):
            try:
                attrs = self.service_validate(attrs)
            except ServiceException as e:
                self.handle_service_exception(e)
        
        return attrs


class TenantAwareSerializer(BaseServiceSerializer):
    """
    Serializer for models that are tenant-aware
    Automatically filters querysets by tenant context
    """
    
    def get_queryset(self):
        """Get queryset filtered by tenant context"""
        tenant = self.context.get('tenant')
        if not tenant:
            raise TenantException("Tenant context required")
        
        queryset = self.Meta.model.objects.all()
        
        # Filter by tenant if model has tenant relationship
        if hasattr(self.Meta.model, 'tenant'):
            queryset = queryset.filter(tenant=tenant)
        elif hasattr(self.Meta.model, 'school'):
            queryset = queryset.filter(school=tenant)
        
        return queryset


class ReadOnlyServiceSerializer(ServiceSerializerMixin, serializers.ModelSerializer):
    """
    Read-only serializer that can use services for complex data retrieval
    but doesn't support create/update operations
    """
    
    def create(self, validated_data):
        raise NotImplementedError("ReadOnlyServiceSerializer doesn't support create")
    
    def update(self, instance, validated_data):
        raise NotImplementedError("ReadOnlyServiceSerializer doesn't support update")