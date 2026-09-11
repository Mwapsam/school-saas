"""Employee exit / offboarding endpoints — mounted under /api/portal/hr/.

Read: ``hr.exit.view``. Write: ``hr.exit.manage``.
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import EmployeeExit, ExitClearanceItem
from core.services.hr_exit_service import ExitService

from .permissions import HasHRPermission, IsHR
from .hr_views import _forbidden, _held, _paginate, _tenant


class ClearanceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExitClearanceItem
        fields = ["id", "label", "order", "is_done", "done_at", "note"]


class ExitSerializer(serializers.ModelSerializer):
    clearance_items = ClearanceItemSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    department = serializers.CharField(source="employee.employee_department.name", default=None, read_only=True)
    exit_type_label = serializers.CharField(source="get_exit_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EmployeeExit
        fields = [
            "id", "employee_id", "employee_name", "employee_number", "department",
            "exit_type", "exit_type_label", "notice_date", "last_working_date",
            "reason", "exit_interview_notes", "final_payment_status",
            "outstanding_leave_days", "handover_status", "status", "status_label",
            "completed_at", "created_at", "progress", "clearance_items",
        ]

    def get_progress(self, obj):
        return obj.clearance_progress()


class ExitStartSerializer(serializers.Serializer):
    exit_type = serializers.ChoiceField(choices=[c[0] for c in EmployeeExit.EXIT_TYPE_CHOICES])
    notice_date = serializers.DateField(required=False, allow_null=True)
    last_working_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class ExitUpdateSerializer(serializers.Serializer):
    exit_type = serializers.ChoiceField(choices=[c[0] for c in EmployeeExit.EXIT_TYPE_CHOICES], required=False)
    notice_date = serializers.DateField(required=False, allow_null=True)
    last_working_date = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    exit_interview_notes = serializers.CharField(required=False, allow_blank=True)
    final_payment_status = serializers.ChoiceField(
        choices=[c[0] for c in EmployeeExit.FINAL_PAY_CHOICES], required=False
    )
    outstanding_leave_days = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    handover_status = serializers.ChoiceField(
        choices=[c[0] for c in EmployeeExit.HANDOVER_CHOICES], required=False
    )


class ExitListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.exit.view")]

    def get(self, request):
        service = ExitService(_tenant(request))
        qs = service.list_exits(status=request.query_params.get("status"))
        return _paginate(self, request, qs, ExitSerializer)


class EmployeeExitView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.exit.view")]

    def get(self, request, employee_id):
        exit_row = ExitService(_tenant(request)).get_for_employee(employee_id)
        return Response(ExitSerializer(exit_row).data)

    def post(self, request, employee_id):
        if "hr.exit.manage" not in _held(request):
            return _forbidden("hr.exit.manage")
        ser = ExitStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        exit_row = ExitService(_tenant(request)).start_exit(
            employee_id=employee_id, actor=request.user, **ser.validated_data
        )
        return Response(ExitSerializer(exit_row).data, status=status.HTTP_201_CREATED)


class ExitDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.exit.manage")]

    def patch(self, request, exit_id):
        ser = ExitUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        exit_row = ExitService(_tenant(request)).update_exit(
            exit_id, actor=request.user, **ser.validated_data
        )
        return Response(ExitSerializer(exit_row).data)


class ExitItemView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.exit.manage")]

    def patch(self, request, item_id):
        item = ExitService(_tenant(request)).toggle_item(
            item_id, bool(request.data.get("is_done")),
            actor=request.user, note=request.data.get("note"),
        )
        return Response(ClearanceItemSerializer(item).data)


class ExitCompleteView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.exit.manage")]

    def post(self, request, exit_id):
        exit_row = ExitService(_tenant(request)).complete_exit(exit_id, actor=request.user)
        return Response(ExitSerializer(exit_row).data)
