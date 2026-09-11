"""Onboarding endpoints — mounted under /api/portal/hr/.

Read: ``hr.onboarding.view``. Write (toggle item / add item):
``hr.onboarding.manage``.
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import OnboardingChecklist, OnboardingItem
from core.services.hr_onboarding_service import OnboardingService

from .permissions import HasHRPermission, IsHR
from .hr_views import _forbidden, _held, _paginate, _tenant


class OnboardingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingItem
        fields = ["id", "label", "order", "is_done", "done_at", "note"]


class OnboardingSerializer(serializers.ModelSerializer):
    items = OnboardingItemSerializer(many=True, read_only=True)
    progress = serializers.SerializerMethodField()
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    department = serializers.CharField(source="employee.employee_department.name", default=None, read_only=True)

    class Meta:
        model = OnboardingChecklist
        fields = [
            "id", "employee_id", "employee_name", "employee_number", "department",
            "started_at", "completed_at", "progress", "items",
        ]

    def get_progress(self, obj):
        return obj.progress()


class EmployeeOnboardingView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.onboarding.view")]

    def get(self, request, employee_id):
        checklist = OnboardingService(_tenant(request)).get_for_employee(employee_id)
        return Response(OnboardingSerializer(checklist).data)

    def post(self, request, employee_id):
        """Add a custom checklist item."""
        if "hr.onboarding.manage" not in _held(request):
            return _forbidden("hr.onboarding.manage")
        label = (request.data.get("label") or "").strip()
        item = OnboardingService(_tenant(request)).add_item(
            employee_id, label, actor=request.user
        )
        return Response(OnboardingItemSerializer(item).data, status=status.HTTP_201_CREATED)


class OnboardingItemView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.onboarding.manage")]

    def patch(self, request, item_id):
        item = OnboardingService(_tenant(request)).toggle_item(
            item_id,
            bool(request.data.get("is_done")),
            actor=request.user,
            note=request.data.get("note"),
        )
        return Response(OnboardingItemSerializer(item).data)


class OnboardingListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.onboarding.view")]

    def get(self, request):
        qs = OnboardingService(_tenant(request)).in_progress()
        return _paginate(self, request, qs, OnboardingSerializer)
