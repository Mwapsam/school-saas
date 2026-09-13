"""
HR (Human Resources) domain API — employee, attendance, leave, and performance management.

Note: This API covers employee management, attendance, leave types, and performance reviews.
Future expansions (payroll, training, onboarding, grievances) require additional models.

Reuses existing services: See core/services/hr_*.py
"""

from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import date, timedelta

from core.models import (
    Employee, EmployeeLeave,
)
from core.authz.drf import ModuleEnabled, HasPermission
from core.api.base import TenantAwareViewSet
from core.services.leave_attendance_service import LeaveService
from core.services.exceptions import ValidationException, NotFoundException, BusinessLogicException
from core.serializers.hr_serializers import (
    EmployeeQualificationSerializer, EmployeeDocumentSerializer, EmployeeContractSerializer,
    EmployeeSerializer, LeaveTypeSerializer, LeaveRequestSerializer, AttendanceSerializer,
    PerformanceReviewSerializer, TrainingRecordSerializer, EmployeeExitSerializer,
)


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class EmployeeViewSet(TenantAwareViewSet):
    """
    Employee management — staff directory.

    Covers:
    - List/create/update/delete employees
    - Filter by active status or department
    - Search by name or email
    """
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.employees.view", write="hr.employees.manage"),
    ]
    module = "hr"
    filterset_fields = ['status', 'employment_status', 'employee_department', 'employee_position', 'is_teaching_staff']
    search_fields = ['first_name', 'last_name', 'email', 'employee_number']
    ordering_fields = ['first_name', 'last_name', 'email', 'joining_date', 'created_at']
    ordering = ['first_name', 'last_name']

    def get_queryset(self):
        return super().get_queryset().select_related('employee_department', 'employee_position', 'employee_category')


class EmployeeQualificationViewSet(TenantAwareViewSet):
    """
    Employee qualifications — degrees, certifications.

    Covers:
    - List/create/update/delete qualifications
    - Filter by employee or qualification type
    """
    queryset = EmployeeQualification.objects.all()
    serializer_class = EmployeeQualificationSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.qualifications.view", write="hr.qualifications.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'qualification_type', 'is_highest']
    ordering_fields = ['year_obtained', 'created_at']
    ordering = ['-year_obtained']

    def get_queryset(self):
        return super().get_queryset().select_related('employee')


class EmployeeDocumentViewSet(viewsets.ModelViewSet):
    """
    Employee documents — contracts, certifications, etc.

    Covers:
    - List/create/update/delete documents
    - Filter by employee or document type
    """
    queryset = EmployeeDocument.objects.all()
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.documents.view", write="hr.documents.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'document_type']
    ordering_fields = ['uploaded_at', 'created_at']
    ordering = ['-uploaded_at']

    def get_queryset(self):
        return super().get_queryset().select_related('employee')


class EmployeeContractViewSet(viewsets.ModelViewSet):
    """
    Employee contracts — employment agreements.

    Covers:
    - List/create/update/delete contracts
    - Filter by employee or contract status
    """
    queryset = EmployeeContract.objects.all()
    serializer_class = EmployeeContractSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.contracts.view", write="hr.contracts.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'contract_type', 'renewal_status']
    ordering_fields = ['start_date', 'end_date', 'created_at']
    ordering = ['-start_date']

    def get_queryset(self):
        return super().get_queryset().select_related('employee')


class LeaveTypeViewSet(viewsets.ModelViewSet):
    """
    Leave type management — define leave categories.

    Covers:
    - List/create/update/delete leave types
    - Filter by active status
    """
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.leave-types.view", write="hr.leave-types.manage"),
    ]
    module = "hr"
    filterset_fields = ['status', 'is_paid']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """
    Leave request management — employee leave requests and approvals.

    Covers:
    - List/create/retrieve leave requests
    - Filter by employee, leave type, or status
    - Approve/reject leave via dedicated actions (delegates to LeaveService)

    Update/delete of a submitted request are intentionally not exposed here —
    once submitted, a leave request is either approved or rejected via the
    workflow actions below, matching the legacy template views' behaviour.
    """
    queryset = EmployeeLeave.objects.all()
    serializer_class = LeaveRequestSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.leave.view", write="hr.leave.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'leave_type', 'status']
    search_fields = ['employee__first_name', 'employee__last_name', 'reason']
    ordering_fields = ['start_date', 'end_date', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return super().get_queryset().select_related('employee', 'leave_type', 'approved_by')

    def perform_create(self, serializer):
        data = serializer.validated_data
        try:
            leave = LeaveService(self.request.tenant).request_leave(
                employee_id=str(data['employee'].id),
                leave_type_id=str(data['leave_type'].id) if data.get('leave_type') else None,
                start_date=data['start_date'],
                end_date=data['end_date'],
                reason=data.get('reason', ''),
                user=self.request.user,
            )
        except (ValidationException, NotFoundException, BusinessLogicException) as e:
            raise serializers.ValidationError(str(getattr(e, 'message', e)))
        serializer.instance = leave

    def _acting_employee(self):
        return Employee.objects.filter(tenant=self.request.tenant, user=self.request.user).first()

    @extend_schema(
        description="Approve a leave request",
        request=None,
        responses={200: LeaveRequestSerializer},
    )
    @action(
        detail=True, methods=['post'],
        permission_classes=[IsAuthenticated, ModuleEnabled, HasPermission(read="hr.leave.view", write="hr.leave.approve")],
    )
    def approve(self, request, pk=None):
        """Approve a leave request."""
        try:
            leave = LeaveService(request.tenant).approve_leave(
                pk, self._acting_employee(), remark=request.data.get('remark'),
            )
        except NotFoundException as e:
            return Response({'error': str(e.message)}, status=404)
        return Response(LeaveRequestSerializer(leave).data)

    @extend_schema(
        description="Reject a leave request",
        request=None,
        responses={200: LeaveRequestSerializer},
    )
    @action(
        detail=True, methods=['post'],
        permission_classes=[IsAuthenticated, ModuleEnabled, HasPermission(read="hr.leave.view", write="hr.leave.approve")],
    )
    def reject(self, request, pk=None):
        """Reject a leave request."""
        try:
            leave = LeaveService(request.tenant).reject_leave(
                pk, self._acting_employee(), remark=request.data.get('remark'),
            )
        except NotFoundException as e:
            return Response({'error': str(e.message)}, status=404)
        return Response(LeaveRequestSerializer(leave).data)


class AttendanceViewSet(viewsets.ModelViewSet):
    """
    Attendance management — record and track daily attendance.

    Covers:
    - List/create/update/delete attendance records
    - Filter by employee, date, or status
    - Generate attendance reports
    """
    queryset = EmployeeAttendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.attendance.view", write="hr.attendance.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'date', 'status']
    search_fields = ['employee__first_name', 'employee__last_name']
    ordering_fields = ['date', 'employee', 'created_at']
    ordering = ['-date']

    def get_queryset(self):
        return super().get_queryset().select_related('employee')

    @extend_schema(
        description="Get attendance summary for a date range",
        parameters=[
            OpenApiParameter(name='employee', required=True, description='Employee ID'),
            OpenApiParameter(name='date_from', description='Start date (YYYY-MM-DD)'),
            OpenApiParameter(name='date_to', description='End date (YYYY-MM-DD)'),
        ],
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get attendance summary for employee in date range."""
        employee_id = request.query_params.get('employee')
        if not employee_id:
            return Response({'error': 'employee ID required'}, status=400)

        date_from_str = request.query_params.get('date_from')
        date_to_str = request.query_params.get('date_to')

        try:
            records = EmployeeAttendance.objects.filter(
                employee_id=employee_id,
                tenant=request.tenant
            )
            if date_from_str:
                records = records.filter(date__gte=date_from_str)
            if date_to_str:
                records = records.filter(date__lte=date_to_str)

            present = records.filter(status='present').count()
            absent = records.filter(status='absent').count()
            late = records.filter(status='late').count()

            return Response({
                'employee_id': employee_id,
                'present': present,
                'absent': absent,
                'late': late,
                'total': records.count(),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class PerformanceReviewViewSet(viewsets.ModelViewSet):
    """
    Performance review management — track employee evaluations.

    Covers:
    - List/create/update/delete reviews
    - Filter by employee, review date, or rating
    """
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.reviews.view", write="hr.reviews.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'review_date', 'status', 'is_teacher_review']
    search_fields = ['employee__first_name', 'employee__last_name']
    ordering_fields = ['review_date', 'overall_rating', 'created_at']
    ordering = ['-review_date']

    def get_queryset(self):
        return super().get_queryset().select_related('employee')


class TrainingRecordViewSet(viewsets.ModelViewSet):
    """
    Training records — track employee training attendance.

    Covers:
    - List/create/update/delete training records
    - Filter by employee or training program
    """
    queryset = TrainingRecord.objects.all()
    serializer_class = TrainingRecordSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.training.view", write="hr.training.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'category', 'status', 'is_mandatory']
    search_fields = ['name', 'employee__first_name', 'employee__last_name']
    ordering_fields = ['training_date', 'created_at']
    ordering = ['-training_date']

    def get_queryset(self):
        return super().get_queryset().select_related('employee')


class EmployeeExitViewSet(viewsets.ModelViewSet):
    """
    Employee exit management — offboarding and exit records.

    Covers:
    - List/create/update/delete exit records
    - Filter by exit date or reason
    """
    queryset = EmployeeExit.objects.all()
    serializer_class = EmployeeExitSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled,
        HasPermission(read="hr.exit.view", write="hr.exit.manage"),
    ]
    module = "hr"
    filterset_fields = ['exit_type', 'status', 'final_payment_status']
    search_fields = ['employee__first_name', 'employee__last_name']
    ordering_fields = ['last_working_date', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return super().get_queryset().select_related('employee')
