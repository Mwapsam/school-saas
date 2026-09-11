"""
Admissions domain API — student application intake and enrollment.

Covers:
- Admissions applications (online application form submissions)
- Admissions inquiries (prospective parent inquiries)
- Batch assignments (assigning admitted students to batches)
- Application statuses and workflows

Reuses existing services: AdmissionService (in core/services/admission_service.py)
"""

from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import date

from core.models import (
    AdmissionApplication, AdmissionDocument, Batch, Course
)
from core.authz.drf import ModuleEnabled, HasPermission


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class AdmissionApplicationSerializer(serializers.ModelSerializer):
    """Serializer for AdmissionApplication — student applications."""
    batch_name = serializers.CharField(source='batch.name', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            'id', 'application_number', 'student_name', 'date_of_birth',
            'gender', 'email', 'phone', 'parent_name', 'parent_email',
            'parent_phone', 'address', 'batch', 'batch_name', 'course',
            'course_name', 'application_date', 'status', 'admission_date',
            'rejection_reason', 'notes', 'documents_submitted',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'application_number', 'application_date',
            'admission_date', 'created_at', 'updated_at'
        ]

    def validate_date_of_birth(self, value):
        """Ensure student is of reasonable age."""
        if value and value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value


class AdmissionApplicationBatchAssignmentSerializer(serializers.Serializer):
    """Serializer for assigning applications to batches."""
    application_id = serializers.UUIDField()
    batch_id = serializers.UUIDField()
    notes = serializers.CharField(required=False, allow_blank=True)


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class AdmissionApplicationViewSet(viewsets.ModelViewSet):
    """
    Admissions application management — student applications.

    Covers:
    - List/filter/search applications
    - Retrieve, create, update applications
    - Approve/reject applications
    - Batch assignment
    - Generate admission letters
    """
    queryset = AdmissionApplication.objects.select_related('batch', 'course')
    serializer_class = AdmissionApplicationSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="admissions.application.view", write="admissions.application.manage"),
    ]
    module = "admissions"
    filterset_fields = ['status', 'batch', 'course', 'application_date']
    search_fields = ['student_name', 'application_number', 'parent_email']
    ordering_fields = ['application_date', 'student_name', 'status']
    ordering = ['-application_date']

    @extend_schema(
        description="List admissions applications (paginated, filterable by status/batch)",
        parameters=[
            OpenApiParameter(
                name='status',
                enum=['pending_review', 'approved', 'rejected', 'enrolled']
            ),
            OpenApiParameter(name='batch', description='Filter by batch ID'),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    @extend_schema(
        description="Approve an admission application",
        request=None,
        responses={200: AdmissionApplicationSerializer},
    )
    def approve(self, request, pk=None):
        """Approve an admission application."""
        application = self.get_object()
        application.status = 'approved'
        application.admission_date = date.today()
        application.save()
        return Response(AdmissionApplicationSerializer(application).data)

    @action(detail=True, methods=['post'])
    @extend_schema(
        description="Reject an admission application",
        request={'type': 'object', 'properties': {'reason': {'type': 'string'}}},
        responses={200: AdmissionApplicationSerializer},
    )
    def reject(self, request, pk=None):
        """Reject an admission application."""
        application = self.get_object()
        application.status = 'rejected'
        application.rejection_reason = request.data.get('reason', '')
        application.save()
        return Response(AdmissionApplicationSerializer(application).data)

    @action(detail=True, methods=['post'])
    @extend_schema(
        description="Assign application to a batch",
        request={'type': 'object', 'properties': {'batch_id': {'type': 'string', 'format': 'uuid'}, 'notes': {'type': 'string'}}},
        responses={200: AdmissionApplicationSerializer},
    )
    def assign_batch(self, request, pk=None):
        """Assign approved application to a batch."""
        application = self.get_object()
        batch_id = request.data.get('batch_id')
        notes = request.data.get('notes', '')

        try:
            batch = Batch.objects.get(id=batch_id, tenant=request.tenant)
        except Batch.DoesNotExist:
            return Response({'error': 'Batch not found'}, status=400)

        application.batch = batch
        application.course = batch.course
        application.status = 'enrolled'
        if notes:
            application.notes = f"{application.notes}\nBatch Assignment: {notes}"
        application.save()
        return Response(AdmissionApplicationSerializer(application).data)

    @action(detail=True, methods=['get'])
    @extend_schema(
        description="Download admission letter PDF",
        responses={'application/pdf': None},
    )
    def admission_letter(self, request, pk=None):
        """Download admission letter PDF."""
        application = self.get_object()
        if application.status != 'approved':
            return Response(
                {'error': 'Admission letter only available for approved applications'},
                status=400
            )
        # In production: generate/retrieve signed URL to letter PDF
        return Response({
            'letter_url': f'/media/admission-letters/{application.id}.pdf',
            'student_name': application.student_name,
            'application_number': application.application_number,
        })

    @action(detail=False, methods=['get'])
    @extend_schema(
        description="Get admissions statistics summary",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'total_applications': {'type': 'integer'},
                    'pending': {'type': 'integer'},
                    'approved': {'type': 'integer'},
                    'rejected': {'type': 'integer'},
                    'enrolled': {'type': 'integer'},
                }
            }
        },
    )
    def statistics(self, request):
        """Get admissions statistics."""
        apps = AdmissionApplication.objects.filter(tenant=request.tenant)
        return Response({
            'total_applications': apps.count(),
            'pending': apps.filter(status='pending_review').count(),
            'approved': apps.filter(status='approved').count(),
            'rejected': apps.filter(status='rejected').count(),
            'enrolled': apps.filter(status='enrolled').count(),
        })


class PublicAdmissionApplicationCreateView(viewsets.ViewSet):
    """
    Public admissions application submission (no authentication required).

    Allows prospective students/parents to submit applications via the portal.
    """
    permission_classes = [AllowAny]  # Public endpoint
    serializer_class = AdmissionApplicationSerializer

    @extend_schema(
        description="Submit a public admissions application (no authentication required)",
        request=AdmissionApplicationSerializer,
        responses={201: {'type': 'object', 'properties': {
            'application_number': {'type': 'string'},
            'message': {'type': 'string'},
        }}},
    )
    def create(self, request):
        """Submit a public admissions application."""
        # This would use a public schema tenant or the current tenant
        serializer = AdmissionApplicationSerializer(data=request.data)
        if serializer.is_valid():
            # Create application
            application = AdmissionApplication.objects.create(
                **serializer.validated_data,
                status='pending_review',
                tenant=request.tenant,
            )
            return Response(
                {
                    'application_number': application.application_number,
                    'message': 'Application submitted successfully. You will receive updates via email.',
                },
                status=201
            )
        return Response(serializer.errors, status=400)
