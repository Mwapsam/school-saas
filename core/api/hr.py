"""
HR (Human Resources) domain API — consolidates 9 view modules into coherent endpoints.

Covers:
- Employee management (staff directory, roles, contracts, documents, qualifications)
- Payroll (payroll runs, payslips, salary structures)
- Leave management (leave types, requests, balances, approvals)
- Attendance tracking (records, registers, reports)
- Training & development (programs, attendance, certificates)
- Performance management (reviews, ratings, goals)
- Disciplinary & grievances (cases, actions, resolutions)
- Onboarding & exit (checklists, handover, offboarding)
- HR policies & acknowledgments

Reuses existing services: HRService, PayrollService, LeaveService, etc.
(See core/services/hr_*.py)
"""

from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import date, timedelta

from core.models import (
    Employee, EmployeeContract, EmployeeQualification, EmployeeDocument,
    PayrollRun, PayslipTemplate, LeaveType, LeaveRequest, Attendance,
    Training, TrainingAttendance, PerformanceReview, EmployeeDisciplinary,
    EmployeeGrievance, EmployeeOnboarding, EmployeeExit, HRPolicy,
    PolicyAcknowledgment, EmployeeRole
)
from core.authz.drf import ModuleEnabled, HasPermission


# ───────────────────────────────────────────────────────────────────────────
# Serializers
# ───────────────────────────────────────────────────────────────────────────

class EmployeeRoleSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeRole — job titles."""
    class Meta:
        model = EmployeeRole
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeQualificationSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeQualification — degrees, certifications."""
    class Meta:
        model = EmployeeQualification
        fields = [
            'id', 'qualification_name', 'institution', 'grade_obtained',
            'date_obtained', 'certificate_file', 'is_verified',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeDocument — contracts, certificates, licenses."""
    class Meta:
        model = EmployeeDocument
        fields = [
            'id', 'document_type', 'document_file', 'uploaded_date',
            'expiry_date', 'is_verified', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeContractSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeContract — employment agreements."""
    class Meta:
        model = EmployeeContract
        fields = [
            'id', 'contract_type', 'start_date', 'end_date',
            'salary', 'job_title', 'department', 'is_active',
            'contract_file', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeSerializer(serializers.ModelSerializer):
    """Serializer for Employee — main staff record."""
    role_name = serializers.CharField(source='role.name', read_only=True)
    qualifications = EmployeeQualificationSerializer(many=True, read_only=True)
    documents = EmployeeDocumentSerializer(many=True, read_only=True)
    contracts = EmployeeContractSerializer(many=True, read_only=True)

    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'email', 'phone',
            'date_of_birth', 'gender', 'role', 'role_name',
            'department', 'hire_date', 'is_active',
            'qualifications', 'documents', 'contracts',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'employee_id', 'created_at', 'updated_at']


class LeaveTypeSerializer(serializers.ModelSerializer):
    """Serializer for LeaveType — annual leave, sick leave, etc."""
    class Meta:
        model = LeaveType
        fields = [
            'id', 'name', 'code', 'allowed_days', 'is_paid',
            'requires_approval', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LeaveRequestSerializer(serializers.ModelSerializer):
    """Serializer for LeaveRequest — time-off requests."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'employee_name', 'leave_type', 'leave_type_name',
            'start_date', 'end_date', 'reason', 'status', 'approved_by',
            'approval_date', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'approved_by', 'approval_date', 'created_at', 'updated_at']


class AttendanceSerializer(serializers.ModelSerializer):
    """Serializer for Attendance — daily attendance records."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'employee', 'employee_name', 'date', 'check_in_time',
            'check_out_time', 'status', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TrainingSerializer(serializers.ModelSerializer):
    """Serializer for Training — professional development programs."""
    class Meta:
        model = Training
        fields = [
            'id', 'name', 'description', 'start_date', 'end_date',
            'location', 'trainer', 'cost', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TrainingAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for TrainingAttendance — who attended what training."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    training_name = serializers.CharField(source='training.name', read_only=True)

    class Meta:
        model = TrainingAttendance
        fields = [
            'id', 'employee', 'employee_name', 'training', 'training_name',
            'attendance_status', 'certification_received', 'certificate_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PerformanceReviewSerializer(serializers.ModelSerializer):
    """Serializer for PerformanceReview — annual/periodic evaluations."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    reviewer_name = serializers.CharField(source='reviewer.full_name', read_only=True)

    class Meta:
        model = PerformanceReview
        fields = [
            'id', 'employee', 'employee_name', 'review_period',
            'reviewer', 'reviewer_name', 'rating', 'strengths',
            'areas_for_improvement', 'goals_for_next_period',
            'overall_comments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeDisciplinarySerializer(serializers.ModelSerializer):
    """Serializer for EmployeeDisciplinary — misconduct cases."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = EmployeeDisciplinary
        fields = [
            'id', 'employee', 'employee_name', 'incident_date',
            'description', 'severity', 'action_taken', 'status',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeGrievanceSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeGrievance — complaints and resolutions."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = EmployeeGrievance
        fields = [
            'id', 'employee', 'employee_name', 'grievance_date',
            'description', 'category', 'status', 'resolution',
            'resolution_date', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeOnboardingSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeOnboarding — new hire checklist."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = EmployeeOnboarding
        fields = [
            'id', 'employee', 'employee_name', 'onboarding_date',
            'orientation_completed', 'orientation_date', 'equipment_issued',
            'access_granted', 'policy_acknowledged', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EmployeeExitSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeExit — offboarding process."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = EmployeeExit
        fields = [
            'id', 'employee', 'employee_name', 'exit_date',
            'reason_for_exit', 'exit_interview_date', 'final_settlement_date',
            'equipment_returned', 'access_revoked', 'status',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class HRPolicySerializer(serializers.ModelSerializer):
    """Serializer for HRPolicy — company policies."""
    class Meta:
        model = HRPolicy
        fields = [
            'id', 'title', 'description', 'policy_file', 'effective_date',
            'version', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PolicyAcknowledgmentSerializer(serializers.ModelSerializer):
    """Serializer for PolicyAcknowledgment — employee policy sign-offs."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    policy_title = serializers.CharField(source='policy.title', read_only=True)

    class Meta:
        model = PolicyAcknowledgment
        fields = [
            'id', 'employee', 'employee_name', 'policy', 'policy_title',
            'acknowledged_date', 'acknowledged_by', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ───────────────────────────────────────────────────────────────────────────
# ViewSets
# ───────────────────────────────────────────────────────────────────────────

class EmployeeRoleViewSet(viewsets.ModelViewSet):
    """Employee role/job title management."""
    queryset = EmployeeRole.objects.all()
    serializer_class = EmployeeRoleSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.employee.view", write="hr.employee.manage"),
    ]
    module = "hr"
    filterset_fields = ['is_active']
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    Employee management — main staff directory.

    Covers:
    - List/filter/search all employees
    - Retrieve, create, update, delete employees
    - Nested: qualifications, documents, contracts
    """
    queryset = Employee.objects.prefetch_related(
        'qualifications', 'documents', 'contracts'
    ).select_related('role')
    serializer_class = EmployeeSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.employee.view", write="hr.employee.manage"),
    ]
    module = "hr"
    filterset_fields = ['role', 'is_active', 'department']
    search_fields = ['full_name', 'email', 'employee_id']
    ordering_fields = ['full_name', 'hire_date']
    ordering = ['full_name']

    @extend_schema(
        description="List all employees (paginated, filterable by role/department)",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class LeaveTypeViewSet(viewsets.ModelViewSet):
    """Leave type definitions (annual leave, sick leave, maternity, etc.)."""
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.leave.view", write="hr.leave.manage"),
    ]
    module = "hr"
    filterset_fields = ['is_paid', 'is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name']
    ordering = ['name']


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """
    Leave request management — employees request time off.

    Covers:
    - List/filter leave requests
    - Create, retrieve, update, delete requests
    - Approve/reject leave (custom actions)
    """
    queryset = LeaveRequest.objects.select_related('employee', 'leave_type', 'approved_by')
    serializer_class = LeaveRequestSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.leave.view", write="hr.leave.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'leave_type', 'status']
    search_fields = ['employee__full_name', 'reason']
    ordering_fields = ['start_date', 'created_at']
    ordering = ['-start_date']

    @action(detail=True, methods=['post'])
    @extend_schema(description="Approve a leave request")
    def approve(self, request, pk=None):
        """Approve a leave request."""
        leave_req = self.get_object()
        leave_req.status = 'approved'
        leave_req.approved_by = request.user
        leave_req.approval_date = date.today()
        leave_req.save()
        return Response(LeaveRequestSerializer(leave_req).data)

    @action(detail=True, methods=['post'])
    @extend_schema(description="Reject a leave request")
    def reject(self, request, pk=None):
        """Reject a leave request."""
        leave_req = self.get_object()
        leave_req.status = 'rejected'
        leave_req.save()
        return Response(LeaveRequestSerializer(leave_req).data)


class AttendanceViewSet(viewsets.ModelViewSet):
    """
    Attendance tracking — daily check-in/out records.

    Covers:
    - Log attendance
    - Filter by date range, employee, status
    - Generate attendance reports
    """
    queryset = Attendance.objects.select_related('employee')
    serializer_class = AttendanceSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.attendance.view", write="hr.attendance.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'status', 'date']
    search_fields = ['employee__full_name']
    ordering_fields = ['date', 'employee']
    ordering = ['-date']

    @action(detail=False, methods=['get'])
    @extend_schema(
        description="Get attendance report for an employee",
        parameters=[
            OpenApiParameter(name='employee', required=True),
            OpenApiParameter(name='from_date', description='YYYY-MM-DD'),
            OpenApiParameter(name='to_date', description='YYYY-MM-DD'),
        ],
    )
    def employee_report(self, request):
        """Attendance report for a specific employee."""
        employee_id = request.query_params.get('employee')
        from_date = request.query_params.get('from_date', date.today() - timedelta(days=30))
        to_date = request.query_params.get('to_date', date.today())

        records = Attendance.objects.filter(
            employee_id=employee_id,
            date__gte=from_date,
            date__lte=to_date,
            tenant=request.tenant
        ).order_by('date')

        present = records.filter(status='present').count()
        absent = records.filter(status='absent').count()
        late = records.filter(status='late').count()

        return Response({
            'employee_id': employee_id,
            'period': f'{from_date} to {to_date}',
            'present': present,
            'absent': absent,
            'late': late,
            'total_working_days': present + absent + late,
        })


class TrainingViewSet(viewsets.ModelViewSet):
    """Training program management."""
    queryset = Training.objects.all()
    serializer_class = TrainingSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.training.view", write="hr.training.manage"),
    ]
    module = "hr"
    filterset_fields = ['is_active']
    search_fields = ['name', 'trainer']
    ordering_fields = ['start_date', 'name']
    ordering = ['-start_date']


class TrainingAttendanceViewSet(viewsets.ModelViewSet):
    """Who attended which training programs."""
    queryset = TrainingAttendance.objects.select_related('employee', 'training')
    serializer_class = TrainingAttendanceSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.training.view", write="hr.training.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'training', 'attendance_status', 'certification_received']
    search_fields = ['employee__full_name', 'training__name']
    ordering_fields = ['training__start_date']
    ordering = ['-training__start_date']


class PerformanceReviewViewSet(viewsets.ModelViewSet):
    """Performance review and evaluation management."""
    queryset = PerformanceReview.objects.select_related('employee', 'reviewer')
    serializer_class = PerformanceReviewSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.performance.view", write="hr.performance.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'reviewer', 'review_period']
    search_fields = ['employee__full_name', 'overall_comments']
    ordering_fields = ['review_period', 'rating']
    ordering = ['-review_period']


class EmployeeDisciplinaryViewSet(viewsets.ModelViewSet):
    """Disciplinary case management."""
    queryset = EmployeeDisciplinary.objects.select_related('employee')
    serializer_class = EmployeeDisciplinarySerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.disciplinary.view", write="hr.disciplinary.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'severity', 'status']
    search_fields = ['employee__full_name', 'description']
    ordering_fields = ['incident_date']
    ordering = ['-incident_date']


class EmployeeGrievanceViewSet(viewsets.ModelViewSet):
    """Grievance and complaint management."""
    queryset = EmployeeGrievance.objects.select_related('employee')
    serializer_class = EmployeeGrievanceSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.grievance.view", write="hr.grievance.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'category', 'status']
    search_fields = ['employee__full_name', 'description']
    ordering_fields = ['grievance_date']
    ordering = ['-grievance_date']


class EmployeeOnboardingViewSet(viewsets.ModelViewSet):
    """New employee onboarding checklist."""
    queryset = EmployeeOnboarding.objects.select_related('employee')
    serializer_class = EmployeeOnboardingSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.employee.view", write="hr.employee.manage"),
    ]
    module = "hr"
    filterset_fields = ['status', 'orientation_completed']
    search_fields = ['employee__full_name']
    ordering_fields = ['onboarding_date']
    ordering = ['-onboarding_date']


class EmployeeExitViewSet(viewsets.ModelViewSet):
    """Employee offboarding/exit management."""
    queryset = EmployeeExit.objects.select_related('employee')
    serializer_class = EmployeeExitSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.employee.view", write="hr.employee.manage"),
    ]
    module = "hr"
    filterset_fields = ['status', 'reason_for_exit']
    search_fields = ['employee__full_name']
    ordering_fields = ['exit_date']
    ordering = ['-exit_date']


class HRPolicyViewSet(viewsets.ModelViewSet):
    """HR policy documents."""
    queryset = HRPolicy.objects.all()
    serializer_class = HRPolicySerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.policy.view", write="hr.policy.manage"),
    ]
    module = "hr"
    filterset_fields = ['is_active']
    search_fields = ['title', 'description']
    ordering_fields = ['effective_date', 'version']
    ordering = ['-effective_date']


class PolicyAcknowledgmentViewSet(viewsets.ModelViewSet):
    """Policy acknowledgments — who signed off on what policies."""
    queryset = PolicyAcknowledgment.objects.select_related('employee', 'policy')
    serializer_class = PolicyAcknowledgmentSerializer
    permission_classes = [
        IsAuthenticated,
        ModuleEnabled("hr"),
        HasPermission(read="hr.policy.view", write="hr.policy.manage"),
    ]
    module = "hr"
    filterset_fields = ['employee', 'policy']
    search_fields = ['employee__full_name', 'policy__title']
    ordering_fields = ['acknowledged_date']
    ordering = ['-acknowledged_date']
