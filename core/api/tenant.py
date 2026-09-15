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

from datetime import timedelta

from django.utils import timezone
from django.utils.crypto import get_random_string
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
from core.services.exceptions import ServiceException
from core.services.tenant_provisioning import (
    create_tenant_superuser,
    provision_default_modules,
    provision_school,
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
        """Provision a real tenant from this demo request: creates the School
        (schema + migrations, via the same service the CLI provisioning
        commands use), its primary domain, a trial billing status (see
        School.billing_status — Day 1), default (disabled) module rows, and
        a first admin user for the school. Payment stays manual: this only
        starts the trial clock, it does not charge anyone.

        Required body fields: code, schema_name, domain.
        Optional: extra_domains (list[str]), country_code, trial_days
        (default 14), admin_username, admin_email (defaults to the request's
        email), admin_password (auto-generated and returned once if omitted),
        admin_first_name/admin_last_name (defaulted from full_name).
        """
        demo_request = self.get_object()

        if demo_request.converted_school_id:
            return Response(
                {"error": "This request has already been converted.",
                 "school_id": demo_request.converted_school_id},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data
        code = (data.get("code") or "").strip()
        schema_name = (data.get("schema_name") or "").strip()
        domain = (data.get("domain") or "").strip()
        missing = [f for f, v in (("code", code), ("schema_name", schema_name), ("domain", domain)) if not v]
        if missing:
            return Response(
                {"error": f"Missing required field(s): {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first_name, _, last_name = (demo_request.full_name or "").partition(" ")
        admin_email = data.get("admin_email") or demo_request.email
        admin_username = data.get("admin_username") or admin_email.split("@")[0]
        generated_password = None
        admin_password = data.get("admin_password")
        if not admin_password:
            generated_password = get_random_string(12)
            admin_password = generated_password

        try:
            result = provision_school(
                name=demo_request.school_name or demo_request.full_name,
                code=code,
                schema_name=schema_name,
                domain=domain,
                extra_domains=data.get("extra_domains"),
                country_code=data.get("country_code"),
                email=demo_request.email,
                phone=demo_request.phone or None,
            )
            school = result.school

            trial_days = int(data.get("trial_days") or 14)
            school.billing_status = School.BILLING_STATUS_TRIAL
            school.trial_ends_at = timezone.now() + timedelta(days=trial_days)
            school.save(update_fields=["billing_status", "trial_ends_at"])

            provision_default_modules(school)

            admin_user, admin_created = create_tenant_superuser(
                school,
                username=admin_username,
                email=admin_email,
                password=admin_password,
                first_name=data.get("admin_first_name") or first_name,
                last_name=data.get("admin_last_name") or last_name,
            )
        except ServiceException as exc:
            return Response(
                {"error": exc.message, "details": exc.details},
                status=status.HTTP_400_BAD_REQUEST,
            )

        demo_request.status = "converted"
        demo_request.converted_school = school
        demo_request.save(update_fields=["status", "converted_school", "updated_at"])

        return Response({
            "status": "converted",
            "school": {
                "id": school.id,
                "name": school.name,
                "code": school.code,
                "schema_name": school.schema_name,
                "domain": domain,
                "billing_status": school.billing_status,
                "trial_ends_at": school.trial_ends_at,
            },
            "admin_user": {
                "username": admin_user.username,
                "email": admin_user.email,
                "created": admin_created,
                # Only present when a password was auto-generated — this is the
                # only time it is ever returned in plaintext.
                "generated_password": generated_password,
            },
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Mark request as rejected (not moving forward)."""
        demo_request = self.get_object()
        demo_request.status = 'rejected'
        demo_request.save()
        return Response({'status': 'marked as rejected'})

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending demo requests."""
        pending = self.queryset.filter(status='pending')
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)
