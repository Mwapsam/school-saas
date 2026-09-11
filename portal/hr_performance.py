"""Performance-review endpoints — mounted under /api/portal/hr/.

Read: ``hr.performance.view``. Write: ``hr.performance.conduct``.
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import PerformanceCriterion, PerformanceReview
from core.services.hr_performance_service import PerformanceService

from .permissions import HasHRPermission, IsHR
from .hr_views import _forbidden, _held, _paginate, _tenant


class CriterionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceCriterion
        fields = ["id", "name", "order", "rating", "comment"]


class ReviewSerializer(serializers.ModelSerializer):
    criteria = CriterionSerializer(many=True, read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    reviewer_name = serializers.CharField(source="reviewer.full_name", default=None, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PerformanceReview
        fields = [
            "id", "employee_id", "employee_name", "employee_number", "reviewer_id",
            "reviewer_name", "review_period", "review_date", "status", "status_label",
            "is_teacher_review", "overall_rating", "objectives", "strengths",
            "improvement_areas", "development_actions", "reviewer_comments",
            "employee_comments", "next_review_date", "completed_at", "created_at",
            "criteria",
        ]


class ReviewCreateSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()
    review_period = serializers.CharField()
    review_date = serializers.DateField()
    reviewer_id = serializers.UUIDField(required=False, allow_null=True)
    is_teacher_review = serializers.BooleanField(required=False, allow_null=True)


class ReviewUpdateSerializer(serializers.Serializer):
    review_period = serializers.CharField(required=False)
    review_date = serializers.DateField(required=False)
    reviewer_id = serializers.UUIDField(required=False, allow_null=True)
    overall_rating = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=5)
    objectives = serializers.CharField(required=False, allow_blank=True)
    strengths = serializers.CharField(required=False, allow_blank=True)
    improvement_areas = serializers.CharField(required=False, allow_blank=True)
    development_actions = serializers.CharField(required=False, allow_blank=True)
    reviewer_comments = serializers.CharField(required=False, allow_blank=True)
    employee_comments = serializers.CharField(required=False, allow_blank=True)
    next_review_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=[c[0] for c in PerformanceReview.STATUS_CHOICES], required=False
    )
    criteria = serializers.ListField(child=serializers.DictField(), required=False)


class ReviewListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.performance.view")]

    def get(self, request):
        service = PerformanceService(_tenant(request))
        qs = service.list_reviews(status=request.query_params.get("status"))
        return _paginate(self, request, qs, ReviewSerializer)

    def post(self, request):
        if "hr.performance.conduct" not in _held(request):
            return _forbidden("hr.performance.conduct")
        ser = ReviewCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        review = PerformanceService(_tenant(request)).create_review(
            actor=request.user, **ser.validated_data
        )
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class EmployeeReviewsView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.performance.view")]

    def get(self, request, employee_id):
        qs = PerformanceService(_tenant(request)).list_reviews(employee_id=employee_id)
        return Response(ReviewSerializer(qs, many=True).data)


class ReviewDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.performance.view")]

    def get(self, request, review_id):
        service = PerformanceService(_tenant(request))
        return Response(ReviewSerializer(service.get_by_id(review_id)).data)

    def patch(self, request, review_id):
        if "hr.performance.conduct" not in _held(request):
            return _forbidden("hr.performance.conduct")
        ser = ReviewUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        criteria = data.pop("criteria", None)
        service = PerformanceService(_tenant(request))
        if data:
            service.update_review(review_id, actor=request.user, **data)
        if criteria is not None:
            service.set_criteria(review_id, criteria, actor=request.user)
        return Response(ReviewSerializer(service.get_by_id(review_id)).data)


class ReviewCompleteView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.performance.conduct")]

    def post(self, request, review_id):
        review = PerformanceService(_tenant(request)).complete_review(
            review_id, actor=request.user
        )
        return Response(ReviewSerializer(review).data)


# ── Self-service: an employee's own reviews ─────────────────────────────
from .permissions import IsLinkedEmployee  # noqa: E402


class MyReviewsView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def get(self, request):
        qs = PerformanceReview.objects.filter(
            tenant=request.employee.tenant, employee=request.employee,
        ).exclude(status="draft").prefetch_related("criteria").order_by("-review_date")
        return Response(ReviewSerializer(qs, many=True).data)


class MyReviewDetailView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def _get(self, request, review_id):
        try:
            return PerformanceReview.objects.prefetch_related("criteria").get(
                id=review_id, tenant=request.employee.tenant, employee=request.employee,
            )
        except PerformanceReview.DoesNotExist:
            return None

    def get(self, request, review_id):
        review = self._get(request, review_id)
        if not review or review.status == "draft":
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ReviewSerializer(review).data)

    def patch(self, request, review_id):
        review = self._get(request, review_id)
        if not review or review.status == "draft":
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if "employee_comments" in request.data:
            review.employee_comments = request.data["employee_comments"] or ""
        if request.data.get("acknowledge") and review.status in ("in_review", "employee_ack"):
            review.status = "employee_ack"
        review.save(update_fields=["employee_comments", "status", "updated_at"])
        return Response(ReviewSerializer(review).data)
