"""Policy library + acknowledgement endpoints, mounted under /api/portal/hr/.

HR management: read via ``hr.employee.view``, write via ``hr.settings.manage``.
Self-service (``hr/me/policies/...``): any authenticated linked employee.
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import PolicyDocument
from core.services.hr_policy_service import PolicyService

from .permissions import HasHRPermission, IsHR, IsLinkedEmployee
from .hr_views import _forbidden, _held, _paginate, _tenant

_WRITE = "hr.settings.manage"


class PolicySerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    file_url = serializers.SerializerMethodField()
    ack_summary = serializers.SerializerMethodField()

    class Meta:
        model = PolicyDocument
        fields = [
            "id", "title", "category", "category_label", "description",
            "version", "effective_date", "requires_acknowledgement",
            "is_active", "file_url", "ack_summary", "created_at",
        ]

    def get_file_url(self, obj):
        try:
            return obj.file.url if obj.file else None
        except ValueError:
            return None

    def get_ack_summary(self, obj):
        service = self.context.get("service")
        return service.ack_summary(obj) if service else None


class PolicyWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    category = serializers.ChoiceField(
        choices=[c[0] for c in PolicyDocument.CATEGORY_CHOICES], required=False
    )
    description = serializers.CharField(required=False, allow_blank=True)
    version = serializers.CharField(max_length=40, required=False, allow_blank=True)
    effective_date = serializers.DateField(required=False, allow_null=True)
    requires_acknowledgement = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    file = serializers.FileField(required=False, allow_null=True)


class PolicyListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view")]

    def get(self, request):
        service = PolicyService(_tenant(request))
        active = request.query_params.get("active")
        qs = service.list_policies(
            active=None if active is None else active == "true",
            category=request.query_params.get("category"),
        )
        return _paginate(self, request, qs, PolicySerializer, context={"service": service})

    def post(self, request):
        if _WRITE not in _held(request):
            return _forbidden(_WRITE)
        ser = PolicyWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        service = PolicyService(_tenant(request))
        policy = service.create_policy(
            actor=request.user, file=data.pop("file", None), **data
        )
        return Response(
            PolicySerializer(policy, context={"service": service}).data,
            status=status.HTTP_201_CREATED,
        )


class PolicyDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view")]

    def patch(self, request, policy_id):
        if _WRITE not in _held(request):
            return _forbidden(_WRITE)
        ser = PolicyWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        service = PolicyService(_tenant(request))
        policy = service.update_policy(
            policy_id, actor=request.user, file=data.pop("file", None), **data
        )
        return Response(PolicySerializer(policy, context={"service": service}).data)

    def delete(self, request, policy_id):
        if _WRITE not in _held(request):
            return _forbidden(_WRITE)
        PolicyService(_tenant(request)).delete_policy(policy_id, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PolicyAcknowledgementsView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view")]

    def get(self, request, policy_id):
        policy, rows = PolicyService(_tenant(request)).acknowledgement_matrix(policy_id)
        return Response({"policy_id": str(policy.id), "title": policy.title, "rows": rows})


# ── Self-service ─────────────────────────────────────────────────────────
class MyPoliciesView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def get(self, request):
        service = PolicyService(request.employee.tenant)
        outstanding = service.outstanding_for(request.employee)
        acknowledged = service.acknowledged_for(request.employee)
        return Response({
            "outstanding": PolicySerializer(outstanding, many=True).data,
            "acknowledged": [
                {
                    "policy_id": str(a.policy_id),
                    "title": a.policy.title,
                    "version": a.policy.version,
                    "acknowledged_at": a.acknowledged_at.isoformat(),
                }
                for a in acknowledged
            ],
        })


class MyPolicyAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def post(self, request, policy_id):
        ack = PolicyService(request.employee.tenant).acknowledge(
            policy_id, request.employee, note=request.data.get("note", ""),
        )
        return Response(
            {"policy_id": str(ack.policy_id), "acknowledged_at": ack.acknowledged_at.isoformat()},
            status=status.HTTP_201_CREATED,
        )
