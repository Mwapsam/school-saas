"""Training / CPD endpoints — mounted under /api/portal/hr/.

Read: ``hr.training.view``. Write: ``hr.training.manage``.
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import TrainingRecord
from core.services.hr_training_service import TrainingService

from .permissions import HasHRPermission, IsHR
from .hr_views import _forbidden, _held, _paginate, _tenant


class TrainingSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    compliance_status = serializers.SerializerMethodField()
    certificate_url = serializers.SerializerMethodField()

    class Meta:
        model = TrainingRecord
        fields = [
            "id", "employee_id", "employee_name", "employee_number", "name",
            "category", "category_label", "provider", "training_date", "cost",
            "expiry_date", "status", "is_mandatory", "notes", "compliance_status",
            "certificate_url", "created_at",
        ]

    def get_compliance_status(self, obj):
        return obj.compliance_status()

    def get_certificate_url(self, obj):
        try:
            return obj.certificate.url if obj.certificate else None
        except Exception:
            return None


class TrainingWriteSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)
    category = serializers.ChoiceField(
        choices=[c[0] for c in TrainingRecord.CATEGORY_CHOICES], required=False
    )
    provider = serializers.CharField(required=False, allow_blank=True)
    training_date = serializers.DateField(required=False, allow_null=True)
    cost = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    expiry_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=[c[0] for c in TrainingRecord.STATUS_CHOICES], required=False
    )
    is_mandatory = serializers.BooleanField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)


class TrainingListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.training.view")]

    def get(self, request):
        service = TrainingService(_tenant(request))
        qs = service.list_records(
            category=request.query_params.get("category"),
            status=request.query_params.get("status"),
        )
        return _paginate(self, request, qs, TrainingSerializer)

    def post(self, request):
        if "hr.training.manage" not in _held(request):
            return _forbidden("hr.training.manage")
        ser = TrainingWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        employee_id = data.pop("employee_id", None)
        name = data.pop("name", "")
        record = TrainingService(_tenant(request)).create_record(
            employee_id=employee_id, name=name, actor=request.user, **data
        )
        return Response(TrainingSerializer(record).data, status=status.HTTP_201_CREATED)


class EmployeeTrainingView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.training.view")]

    def get(self, request, employee_id):
        qs = TrainingService(_tenant(request)).list_records(employee_id=employee_id)
        return Response(TrainingSerializer(qs, many=True).data)


class TrainingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.training.view")]

    def patch(self, request, record_id):
        if "hr.training.manage" not in _held(request):
            return _forbidden("hr.training.manage")
        ser = TrainingWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        record = TrainingService(_tenant(request)).update_record(
            record_id, actor=request.user, **ser.validated_data
        )
        return Response(TrainingSerializer(record).data)

    def delete(self, request, record_id):
        if "hr.training.manage" not in _held(request):
            return _forbidden("hr.training.manage")
        TrainingService(_tenant(request)).delete_record(record_id, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainingComplianceView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.training.view")]

    def get(self, request):
        service = TrainingService(_tenant(request))
        expiring = service.expiring(mandatory_only=False)
        return Response({
            "mandatory_gaps": service.mandatory_gaps(),
            "expiring": TrainingSerializer(expiring, many=True).data,
        })
