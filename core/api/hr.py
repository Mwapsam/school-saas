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
    Employee, EmployeeContract, EmployeeQualification, EmployeeDocument,
    LeaveType, Attendance, PerformanceReview, TrainingRecord, EmployeeExit
)
from core.authz.drf import ModuleEnabled, HasPermission


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class EmployeeQualificationSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeQualification — degrees, certifications."""
    class Meta:
        model = EmployeeQualification
        fields = ['id', 'employee', 'qualification_type', 'institution', 'year_obtained', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeDocument — contracts, certifications, etc."""
    class Meta:
        model = EmployeeDocument
        fields = ['id', 'employee', 'document_type', 'file', 'uploaded_at', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeContractSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeContract — employment agreements."""
    class Meta:
        model = EmployeeContract
        fields = ['id', 'employee', 'contract_type', 'start_date', 'end_date', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeSerializer(serializers.ModelSerializer):
    """Serializer for Employee — staff directory."""
    class Meta:
        model = Employee
        fields = ['id', 'first_name', 'last_name', 'email', 'phone', 'date_of_birth', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class LeaveTypeSerializer(serializers.ModelSerializer):
    """Serializer for LeaveType — leave categories (sick, vacation, etc.)."""
    class Meta:
        model = LeaveType
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AttendanceSerializer(serializers.ModelSerializer):
    """Serializer for Attendance — daily attendance records."""
    class Meta:
        model = Attendance
        fields = ['id', 'employee', 'date', 'status', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PerformanceReviewSerializer(serializers.ModelSerializer):
    """Serializer for PerformanceReview — annual reviews."""
    class Meta:
        model = PerformanceReview
        fields = ['id', 'employee', 'review_date', 'rating', 'comments', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TrainingRecordSerializer(serializers.ModelSerializer):
    """Serializer for TrainingRecord — training programs attended."""
    class Meta:
        model = TrainingRecord
        fields = ['id', 'employee', 'training_name', 'training_date', 'certificate_received', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeExitSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeExit — exit/offboarding records."""
    class Meta:
        model = EmployeeExit
        fields = ['id', 'employee', 'exit_date', 'reason', 'comments', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class EmployeeViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['is_active']
    search_fields = ['first_name', 'last_name', 'email']
    ordering_fields = ['first_name', 'last_name', 'email', 'created_at']
    ordering = ['first_name', 'last_name']


class EmployeeQualificationViewSet(viewsets.ModelViewSet):
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
    filterset_fields = ['employee', 'qualification_type', 'is_active']
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
    filterset_fields = ['employee', 'contract_type', 'is_active']
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
    filterset_fields = ['is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class AttendanceViewSet(viewsets.ModelViewSet):
    """
    Attendance management — record and track daily attendance.

    Covers:
    - List/create/update/delete attendance records
    - Filter by employee, date, or status
    - Generate attendance reports
    """
    queryset = Attendance.objects.all()
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
            records = Attendance.objects.filter(
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
    filterset_fields = ['employee', 'review_date', 'is_active']
    search_fields = ['employee__first_name', 'employee__last_name']
    ordering_fields = ['review_date', 'rating', 'created_at']
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
    filterset_fields = ['employee', 'certificate_received']
    search_fields = ['training_name', 'employee__first_name', 'employee__last_name']
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
    filterset_fields = ['exit_date', 'reason']
    search_fields = ['employee__first_name', 'employee__last_name']
    ordering_fields = ['exit_date', 'created_at']
    ordering = ['-exit_date']

    def get_queryset(self):
        return super().get_queryset().select_related('employee')
