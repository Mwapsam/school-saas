"""
Base ViewSet classes for all API endpoints.

Ensures:
1. Tenant context is passed to all serializers
2. Pagination, filtering, and ordering are standardized
3. Permission classes follow the TenantAwareSerializer pattern
"""

from rest_framework import viewsets
from django_tenants.models import TenantMixin


class TenantAwareViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that ensures tenant context is passed to serializers.

    All serializers should use TenantAwareSerializer to access tenant from context.
    This base class ensures the tenant is always available.

    Example:
    ```python
    class StudentViewSet(TenantAwareViewSet):
        queryset = Student.objects.all()
        serializer_class = StudentSerializer
    ```
    """

    def get_serializer_context(self):
        """Add tenant to serializer context"""
        context = super().get_serializer_context()
        context['tenant'] = self.request.tenant
        return context

    def get_queryset(self):
        """Filter queryset by tenant"""
        queryset = super().get_queryset()
        tenant = self.request.tenant

        # Filter by tenant if model has tenant field
        if hasattr(self.get_queryset.model, 'tenant'):
            queryset = queryset.filter(tenant=tenant)
        elif hasattr(self.get_queryset.model, 'school'):
            queryset = queryset.filter(school=tenant)

        return queryset


class TenantAwareReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Base read-only ViewSet that ensures tenant context is passed.

    Use this for endpoints that only support list/retrieve (no CRUD).
    """

    def get_serializer_context(self):
        """Add tenant to serializer context"""
        context = super().get_serializer_context()
        context['tenant'] = self.request.tenant
        return context

    def get_queryset(self):
        """Filter queryset by tenant"""
        queryset = super().get_queryset()
        tenant = self.request.tenant

        # Filter by tenant if model has tenant field
        if hasattr(self.get_queryset.model, 'tenant'):
            queryset = queryset.filter(tenant=tenant)
        elif hasattr(self.get_queryset.model, 'school'):
            queryset = queryset.filter(school=tenant)

        return queryset
