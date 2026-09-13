"""
Admissions domain API — student application intake and enrollment.

Covers:
- Admissions applications (online application form submissions)
- Admissions inquiries (prospective parent inquiries)
- Batch assignments (assigning admitted students to batches)
- Application statuses and workflows

Reuses existing services: AdmissionService (in core/services/admission_service.py)
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter

from core.models import (
    AdmissionApplication, Batch, Course
)
from core.authz.drf import ModuleEnabled, HasPermission
from core.services.admission_service import AdmissionService
from core.api.base import TenantAwareViewSet
from core.serializers.admissions_serializers import (
    AdmissionApplicationSerializer, AdmissionApplicationBatchAssignmentSerializer
)


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class AdmissionApplicationViewSet(TenantAwareViewSet):
    """
    Admissions application management — student applications.

    Covers:
    - List/filter/search applications
    - Retrieve, create, update applications
    - Approve/reject applications
    - Batch assignment
    - Generate admission letters
    """
    queryset = AdmissionApplication.objects.select_related('course_applied')
    serializer_class = AdmissionApplicationSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="admissions.application.view", write="admissions.application.manage"),
    ]
    module = "admissions"
    filterset_fields = ['status', 'course_applied', 'application_date']
    search_fields = ['first_name', 'last_name', 'application_number', 'guardian_email']
    ordering_fields = ['application_date', 'last_name', 'status']
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
        reason = request.data.get('reason', '')
        if reason:
            application.remarks = f"{application.remarks}\nRejection reason: {reason}" if application.remarks else f"Rejection reason: {reason}"
        application.save()
        return Response(AdmissionApplicationSerializer(application).data)

    @action(detail=True, methods=['post'])
    @extend_schema(
        description="Assign application to a batch",
        request={'type': 'object', 'properties': {'batch_id': {'type': 'string', 'format': 'uuid'}, 'notes': {'type': 'string'}}},
        responses={200: AdmissionApplicationSerializer},
    )
    def assign_batch(self, request, pk=None):
        """Mark an approved application as enrolled, recording the batch in remarks.

        Note: AdmissionApplication has no `batch` relation on the model — batch
        assignment for enrolled students happens elsewhere (see
        core/view_modules/admission_batch_assignment_views.py). This endpoint
        only validates the batch exists and updates status/remarks accordingly.
        """
        application = self.get_object()
        batch_id = request.data.get('batch_id')
        notes = request.data.get('notes', '')

        try:
            batch = Batch.objects.get(id=batch_id, tenant=request.tenant)
        except Batch.DoesNotExist:
            return Response({'error': 'Batch not found'}, status=400)

        application.status = 'enrolled'
        application.course_applied = batch.course
        assignment_note = f"Batch Assignment: {batch.name}"
        if notes:
            assignment_note += f" — {notes}"
        application.remarks = f"{application.remarks}\n{assignment_note}" if application.remarks else assignment_note
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
            'student_name': f"{application.first_name} {application.last_name}",
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
        serializer = AdmissionApplicationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            course = data.pop('course_applied', None)
            service = AdmissionService(request.tenant)
            application = service.create_application(
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                date_of_birth=data.get('date_of_birth'),
                gender=data.get('gender'),
                course_id=str(course.id) if course else None,
                guardian_name=data.get('guardian_name'),
                guardian_phone=data.get('guardian_phone'),
                address=data.get('address'),
                middle_name=data.get('middle_name'),
                guardian_email=data.get('guardian_email'),
            )
            return Response(
                {
                    'application_number': application.application_number,
                    'message': 'Application submitted successfully. You will receive updates via email.',
                },
                status=201
            )
        return Response(serializer.errors, status=400)
