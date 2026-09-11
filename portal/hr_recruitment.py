"""Recruitment / ATS endpoints — mounted under /api/portal/hr/recruitment/.

Read requires ``hr.recruitment.view``; every write requires
``hr.recruitment.manage`` (checked per-method so a view-only officer still sees
the pipeline).
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Applicant, Vacancy
from core.services.hr_recruitment_service import ApplicantService, VacancyService
from core.services.exceptions import ValidationException

from .permissions import HasHRPermission, IsHR
from .hr_views import HRPagination, _forbidden, _held, _paginate, _tenant


# ── serializers ────────────────────────────────────────────────────────────

class VacancySerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", default=None, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    employment_type_label = serializers.CharField(source="get_employment_type_display", read_only=True)
    applicant_count = serializers.SerializerMethodField()

    class Meta:
        model = Vacancy
        fields = [
            "id", "title", "department_id", "department_name",
            "number_of_positions", "job_description", "employment_type",
            "employment_type_label", "is_teaching_role", "date_advertised",
            "closing_date", "status", "status_label", "applicant_count",
            "created_at",
        ]

    def get_applicant_count(self, obj):
        return getattr(obj, "_applicant_count", None) if hasattr(obj, "_applicant_count") else obj.applicants.count()


class VacancyWriteSerializer(serializers.Serializer):
    title = serializers.CharField()
    department_id = serializers.UUIDField(required=False, allow_null=True)
    number_of_positions = serializers.IntegerField(required=False, min_value=1, default=1)
    job_description = serializers.CharField(required=False, allow_blank=True, default="")
    employment_type = serializers.ChoiceField(
        choices=[c[0] for c in Vacancy.EMPLOYMENT_TYPE_CHOICES], required=False, default="full_time"
    )
    is_teaching_role = serializers.BooleanField(required=False, default=False)
    date_advertised = serializers.DateField(required=False, allow_null=True)
    closing_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=[c[0] for c in Vacancy.STATUS_CHOICES], required=False
    )


class ApplicantSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    stage_label = serializers.CharField(source="get_stage_display", read_only=True)
    vacancy_title = serializers.CharField(source="vacancy.title", read_only=True)
    cv_url = serializers.SerializerMethodField()

    class Meta:
        model = Applicant
        fields = [
            "id", "vacancy_id", "vacancy_title", "first_name", "last_name",
            "full_name", "email", "phone", "qualifications_summary", "stage",
            "stage_label", "stage_changed_at", "interview_date", "interview_panel",
            "interview_score", "interview_comments", "reference_check_notes",
            "decision_notes", "converted_employee_id", "cv_url", "created_at",
        ]

    def get_cv_url(self, obj):
        try:
            return obj.cv.url if obj.cv else None
        except Exception:
            return None


class ApplicantWriteSerializer(serializers.Serializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    qualifications_summary = serializers.CharField(required=False, allow_blank=True, default="")
    cv = serializers.FileField(required=False, allow_null=True)


class StageSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=[c[0] for c in Applicant.STAGE_CHOICES])
    interview_date = serializers.DateField(required=False, allow_null=True)
    interview_panel = serializers.CharField(required=False, allow_blank=True)
    interview_score = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    interview_comments = serializers.CharField(required=False, allow_blank=True)
    reference_check_notes = serializers.CharField(required=False, allow_blank=True)
    decision_notes = serializers.CharField(required=False, allow_blank=True)


class ConvertSerializer(serializers.Serializer):
    employee_number = serializers.CharField()
    joining_date = serializers.DateField()
    gender = serializers.BooleanField()


# ── views ──────────────────────────────────────────────────────────────────

class VacancyListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.recruitment.view")]

    def get(self, request):
        service = VacancyService(_tenant(request))
        qs = service.list_vacancies(status=request.query_params.get("status"))
        return _paginate(self, request, qs, VacancySerializer)

    def post(self, request):
        if "hr.recruitment.manage" not in _held(request):
            return _forbidden("hr.recruitment.manage")
        ser = VacancyWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vacancy = VacancyService(_tenant(request)).create_vacancy(
            actor=request.user, **ser.validated_data
        )
        return Response(VacancySerializer(vacancy).data, status=status.HTTP_201_CREATED)


class VacancyDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.recruitment.view")]

    def get(self, request, vacancy_id):
        service = VacancyService(_tenant(request))
        return Response(VacancySerializer(service.get_by_id(vacancy_id)).data)

    def patch(self, request, vacancy_id):
        if "hr.recruitment.manage" not in _held(request):
            return _forbidden("hr.recruitment.manage")
        ser = VacancyWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        vacancy = VacancyService(_tenant(request)).update_vacancy(
            vacancy_id, actor=request.user, **ser.validated_data
        )
        return Response(VacancySerializer(vacancy).data)


class VacancyApplicantsView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.recruitment.view")]

    def get(self, request, vacancy_id):
        service = ApplicantService(_tenant(request))
        qs = service.list_applicants(
            vacancy_id=vacancy_id, stage=request.query_params.get("stage")
        )
        return Response(ApplicantSerializer(qs, many=True).data)

    def post(self, request, vacancy_id):
        if "hr.recruitment.manage" not in _held(request):
            return _forbidden("hr.recruitment.manage")
        ser = ApplicantWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        applicant = ApplicantService(_tenant(request)).create_applicant(
            vacancy_id=vacancy_id, actor=request.user, **ser.validated_data
        )
        return Response(ApplicantSerializer(applicant).data, status=status.HTTP_201_CREATED)


class ApplicantDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.recruitment.view")]

    def get(self, request, applicant_id):
        service = ApplicantService(_tenant(request))
        return Response(ApplicantSerializer(service.get_by_id(applicant_id)).data)

    def patch(self, request, applicant_id):
        if "hr.recruitment.manage" not in _held(request):
            return _forbidden("hr.recruitment.manage")
        ser = ApplicantWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        applicant = ApplicantService(_tenant(request)).update_applicant(
            applicant_id, actor=request.user, **ser.validated_data
        )
        return Response(ApplicantSerializer(applicant).data)


class ApplicantAdvanceView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.recruitment.manage")]

    def post(self, request, applicant_id):
        ser = StageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        stage = ser.validated_data.pop("stage")
        applicant = ApplicantService(_tenant(request)).advance_stage(
            applicant_id, stage, actor=request.user, **ser.validated_data
        )
        return Response(ApplicantSerializer(applicant).data)


class ApplicantConvertView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.recruitment.manage", "hr.employee.manage")]

    def post(self, request, applicant_id):
        if "hr.employee.manage" not in _held(request):
            return _forbidden("hr.employee.manage")
        ser = ConvertSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        employee = ApplicantService(_tenant(request)).convert_to_employee(
            applicant_id, actor=request.user, **ser.validated_data
        )
        return Response(
            {"employee_id": str(employee.id), "employee_number": employee.employee_number},
            status=status.HTTP_201_CREATED,
        )
