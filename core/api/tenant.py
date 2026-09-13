"""
Tenant (School) provisioning and demo request management APIs.

Endpoints:
  POST   /api/v1/schools/              — Create new school (superuser-only)
  GET    /api/v1/schools/              — List schools (superuser-only)
  GET    /api/v1/schools/{id}/         — Retrieve school (superuser-only)
  PATCH  /api/v1/schools/{id}/         — Update school (superuser-only)
  DELETE /api/v1/schools/{id}/         — Delete school (superuser-only)

  POST   /api/v1/demo-requests/        — Create demo request (public)
  GET    /api/v1/demo-requests/        — List demo requests (superuser-only)
  GET    /api/v1/demo-requests/{id}/   — Retrieve request (superuser-only)
  PATCH  /api/v1/demo-requests/{id}/   — Update request (superuser-only)
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from django_tenants.utils import schema_context

from core.models import School, DemoRequest
from core.serializers.tenant_serializers import (
    SchoolSerializer,
    SchoolListSerializer,
    DemoRequestSerializer,
    DemoRequestAdminSerializer,
)


class SchoolViewSet(viewsets.ModelViewSet):
    """
    Superuser-only viewset for provisioning and managing schools (tenants).

    Requires is_superuser=True (checked via permission_classes).
    """

    queryset = School.objects.all()
    permission_classes = [IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'list':
            return SchoolListSerializer
        return SchoolSerializer

    def perform_create(self, serializer):
        """Create new school. Django-tenants auto-creates the schema."""
        school = serializer.save()
        # Schema auto-creation is handled by School.auto_create_schema = True
        # and django_tenants signals. Just note the successful creation.
        return Response(
            SchoolSerializer(school).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a school."""
        school = self.get_object()
        school.is_active = True
        school.save()
        return Response({'status': 'school activated'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a school."""
        school = self.get_object()
        school.is_active = False
        school.save()
        return Response({'status': 'school deactivated'})


class DemoRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for demo requests.

    Create (POST): Public endpoint, no auth required
    List/Retrieve/Update: Superuser-only
    """

    queryset = DemoRequest.objects.all()

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        if self.request.user.is_authenticated and self.request.user.is_admin:
            return DemoRequestAdminSerializer
        return DemoRequestSerializer

    def perform_create(self, serializer):
        """Create a demo request (public endpoint)."""
        demo_request = serializer.save()
        return demo_request

    @action(detail=True, methods=['post'])
    def contact(self, request, pk=None):
        """Mark request as contacted."""
        demo_request = self.get_object()
        demo_request.status = 'contacted'
        demo_request.save()
        return Response({'status': 'marked as contacted'})

    @action(detail=True, methods=['post'])
    def schedule_demo(self, request, pk=None):
        """Schedule a demo for this request."""
        demo_request = self.get_object()
        demo_request.status = 'demo_scheduled'
        demo_request.save()
        return Response({'status': 'demo scheduled'})

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        """Mark request as converted (became a customer)."""
        demo_request = self.get_object()
        demo_request.status = 'converted'
        demo_request.save()
        return Response({'status': 'marked as converted'})

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending demo requests."""
        pending = self.queryset.filter(status='pending')
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)
