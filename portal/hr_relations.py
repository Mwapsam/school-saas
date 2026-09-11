"""Employee relations — disciplinary & grievance endpoints, mounted under
/api/portal/hr/.

Restricted module. Read: ``hr.disciplinary.view``. Write: ``hr.disciplinary.manage``.
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import DisciplinaryCase, Grievance
from core.services.hr_relations_service import DisciplinaryService, GrievanceService

from .permissions import HasHRPermission, IsHR
from .hr_views import _forbidden, _held, _paginate, _tenant

_READ = "hr.disciplinary.view"
_WRITE = "hr.disciplinary.manage"


# --------------------------------------------------------------------------- #
# Disciplinary
# --------------------------------------------------------------------------- #
class DisciplinarySerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    department = serializers.CharField(source="employee.employee_department.name", default=None, read_only=True)
    case_type_label = serializers.CharField(source="get_case_type_display", read_only=True)
    severity_label = serializers.CharField(source="get_severity_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    outcome_label = serializers.CharField(source="get_outcome_display", read_only=True)

    class Meta:
        model = DisciplinaryCase
        fields = [
            "id", "employee_id", "employee_name", "employee_number", "department",
            "case_type", "case_type_label", "severity", "severity_label",
            "title", "description", "incident_date", "status", "status_label",
            "investigation_notes", "hearing_date", "outcome", "outcome_label",
            "outcome_notes", "action_date", "warning_expiry_date", "appeal_notes",
            "created_at", "closed_at",
        ]


class DisciplinaryCreateSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()
    case_type = serializers.ChoiceField(choices=[c[0] for c in DisciplinaryCase.CASE_TYPE_CHOICES])
    severity = serializers.ChoiceField(
        choices=[c[0] for c in DisciplinaryCase.SEVERITY_CHOICES], required=False, default="minor"
    )
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    incident_date = serializers.DateField(required=False, allow_null=True)


class DisciplinaryUpdateSerializer(serializers.Serializer):
    case_type = serializers.ChoiceField(choices=[c[0] for c in DisciplinaryCase.CASE_TYPE_CHOICES], required=False)
    severity = serializers.ChoiceField(choices=[c[0] for c in DisciplinaryCase.SEVERITY_CHOICES], required=False)
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    incident_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=[c[0] for c in DisciplinaryCase.STATUS_CHOICES], required=False)
    investigation_notes = serializers.CharField(required=False, allow_blank=True)
    hearing_date = serializers.DateField(required=False, allow_null=True)
    outcome = serializers.ChoiceField(choices=[c[0] for c in DisciplinaryCase.OUTCOME_CHOICES], required=False)
    outcome_notes = serializers.CharField(required=False, allow_blank=True)
    action_date = serializers.DateField(required=False, allow_null=True)
    warning_expiry_date = serializers.DateField(required=False, allow_null=True)
    appeal_notes = serializers.CharField(required=False, allow_blank=True)


class DisciplinaryListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_READ)]

    def get(self, request):
        service = DisciplinaryService(_tenant(request))
        qs = service.list_cases(
            status=request.query_params.get("status"),
            employee_id=request.query_params.get("employee"),
        )
        return _paginate(self, request, qs, DisciplinarySerializer)

    def post(self, request):
        if _WRITE not in _held(request):
            return _forbidden(_WRITE)
        ser = DisciplinaryCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        case = DisciplinaryService(_tenant(request)).create_case(
            employee_id=data.pop("employee_id"), actor=request.user, **data
        )
        return Response(DisciplinarySerializer(case).data, status=status.HTTP_201_CREATED)


class DisciplinaryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_READ)]

    def get(self, request, case_id):
        case = DisciplinaryService(_tenant(request)).get_by_id(case_id)
        return Response(DisciplinarySerializer(case).data)

    def patch(self, request, case_id):
        if _WRITE not in _held(request):
            return _forbidden(_WRITE)
        ser = DisciplinaryUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        case = DisciplinaryService(_tenant(request)).update_case(
            case_id, actor=request.user, **ser.validated_data
        )
        return Response(DisciplinarySerializer(case).data)


class EmployeeDisciplinaryView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_READ)]

    def get(self, request, employee_id):
        qs = DisciplinaryService(_tenant(request)).for_employee(employee_id)
        return _paginate(self, request, qs, DisciplinarySerializer)


# --------------------------------------------------------------------------- #
# Grievance
# --------------------------------------------------------------------------- #
class GrievanceSerializer(serializers.ModelSerializer):
    raised_by_name = serializers.CharField(source="raised_by.full_name", read_only=True)
    against_name = serializers.CharField(source="against.full_name", default=None, read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Grievance
        fields = [
            "id", "raised_by_id", "raised_by_name", "against_id", "against_name",
            "category", "category_label", "title", "description", "date_raised",
            "status", "status_label", "review_notes", "resolution_notes",
            "resolved_at", "created_at",
        ]


class GrievanceCreateSerializer(serializers.Serializer):
    raised_by_id = serializers.UUIDField()
    against_id = serializers.UUIDField(required=False, allow_null=True)
    category = serializers.ChoiceField(choices=[c[0] for c in Grievance.CATEGORY_CHOICES])
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    date_raised = serializers.DateField(required=False, allow_null=True)


class GrievanceUpdateSerializer(serializers.Serializer):
    against_id = serializers.UUIDField(required=False, allow_null=True)
    category = serializers.ChoiceField(choices=[c[0] for c in Grievance.CATEGORY_CHOICES], required=False)
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    date_raised = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=[c[0] for c in Grievance.STATUS_CHOICES], required=False)
    review_notes = serializers.CharField(required=False, allow_blank=True)
    resolution_notes = serializers.CharField(required=False, allow_blank=True)


class GrievanceListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_READ)]

    def get(self, request):
        service = GrievanceService(_tenant(request))
        qs = service.list_grievances(
            status=request.query_params.get("status"),
            employee_id=request.query_params.get("employee"),
        )
        return _paginate(self, request, qs, GrievanceSerializer)

    def post(self, request):
        if _WRITE not in _held(request):
            return _forbidden(_WRITE)
        ser = GrievanceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        grievance = GrievanceService(_tenant(request)).create_grievance(
            raised_by_id=data.pop("raised_by_id"), actor=request.user, **data
        )
        return Response(GrievanceSerializer(grievance).data, status=status.HTTP_201_CREATED)


class GrievanceDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_READ)]

    def get(self, request, grievance_id):
        grievance = GrievanceService(_tenant(request)).get_by_id(grievance_id)
        return Response(GrievanceSerializer(grievance).data)

    def patch(self, request, grievance_id):
        if _WRITE not in _held(request):
            return _forbidden(_WRITE)
        ser = GrievanceUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        grievance = GrievanceService(_tenant(request)).update_grievance(
            grievance_id, actor=request.user, **ser.validated_data
        )
        return Response(GrievanceSerializer(grievance).data)
