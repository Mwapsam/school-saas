"""HR portal API — mounted under /api/portal/hr/.

Management endpoints require the ``hr`` role plus a specific ``hr.*`` codename
(:class:`portal.permissions.HasHRPermission`). The ``me/*`` self-service
endpoints only require an authenticated user with a linked, active employee
(:class:`portal.permissions.IsLinkedEmployee`) — never an HR codename — and are
strictly scoped to the caller's own record.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Employee, EmployeeAttendance, EmployeeContract, EmployeeDocument,
    EmployeeLeave, EmployeeQualification, EmploymentHistoryEvent, HRAuditLog,
    HRTask,
)
from core.services.employee_service import EmployeeService
from core.services.hr_contract_service import ContractService
from core.services.hr_document_service import EmployeeDocumentService
from core.services.hr_task_service import HRTaskService
from core.services.leave_attendance_service import AttendanceService, LeaveService
from core.services.exceptions import (
    BusinessLogicException, NotFoundException, ValidationException,
)

from .permissions import HasHRPermission, IsHR, IsLinkedEmployee
from . import hr_selectors
from .hr_serializers import (
    AttendanceMarkSerializer, AttendanceRowSerializer, AuditLogSerializer,
    ContractDecisionSerializer, ContractRenewSerializer, ContractSerializer,
    ContractWriteSerializer, DocumentUploadSerializer, EmployeeCreateSerializer,
    EmployeeDetailSerializer, EmployeeDocumentSerializer, EmployeeListSerializer,
    EmployeeUpdateSerializer, HistoryEventSerializer, HRLeaveSerializer,
    HRTaskSerializer, HRTaskWriteSerializer, LeaveApplySerializer,
    LeaveDecisionSerializer, QualificationSerializer, QualificationWriteSerializer,
)


class HRPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _tenant(request):
    return getattr(request, "tenant", None) or getattr(
        getattr(request, "role_set", None), "employee", None
    ).tenant


def _acting_employee(request):
    """The Employee row for the logged-in HR user, used as ``marked_by`` /
    reviewer on writes. May be ``None``."""
    rs = getattr(request, "role_set", None)
    return getattr(rs, "employee", None)


def _paginate(view, request, queryset, serializer_cls, **ser_kwargs):
    paginator = HRPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    data = serializer_cls(page, many=True, **ser_kwargs).data
    return paginator.get_paginated_response(data)


def _get_employee_or_404(tenant, employee_id):
    try:
        return Employee.objects.get(id=employee_id, tenant=tenant)
    except Employee.DoesNotExist:
        raise NotFoundException(f"Employee {employee_id} not found")


# ── Dashboard ──────────────────────────────────────────────────────────────

class HRDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view")]

    def get(self, request):
        return Response(hr_selectors.hr_dashboard(_tenant(request)))


# ── Employee directory & profile ──────────────────────────────────────────

class EmployeeDirectoryView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view")]

    def get(self, request):
        q = request.query_params
        service = EmployeeService(_tenant(request))
        qs = service.search_employees(
            query=q.get("q"),
            department_id=q.get("department"),
            category_id=q.get("category"),
            position_id=q.get("position"),
            grade_id=q.get("grade"),
            employment_status=q.get("employment_status"),
            contract_type=q.get("contract_type"),
            joined_from=parse_date(q["joined_from"]) if q.get("joined_from") else None,
            joined_to=parse_date(q["joined_to"]) if q.get("joined_to") else None,
            staff_type=q.get("staff_type", "all"),
            active_only=q.get("active_only", "true").lower() != "false",
        ).select_related("employee_department", "employee_position")
        return _paginate(self, request, qs, EmployeeListSerializer)

    def post(self, request):
        if "hr.employee.manage" not in _held(request):
            return _forbidden("hr.employee.manage")
        ser = EmployeeCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        service = EmployeeService(_tenant(request))
        emp = service.create_employee(**ser.validated_data)
        return Response(EmployeeDetailSerializer(emp).data, status=status.HTTP_201_CREATED)


class EmployeeDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view", "hr.employee.manage")]

    def get(self, request, employee_id):
        emp = _get_employee_or_404(_tenant(request), employee_id)
        return Response(EmployeeDetailSerializer(emp).data)

    def patch(self, request, employee_id):
        ser = EmployeeUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        service = EmployeeService(_tenant(request))
        emp = service.update_employee(
            employee_id, actor=request.user, **ser.validated_data
        )
        return Response(EmployeeDetailSerializer(emp).data)


class EmployeeQualificationsView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view")]

    def get(self, request, employee_id):
        qs = EmployeeQualification.objects.filter(
            tenant=_tenant(request), employee_id=employee_id
        )
        return Response(QualificationSerializer(qs, many=True).data)

    def post(self, request, employee_id):
        if "hr.employee.manage" not in _held(request):
            return _forbidden("hr.employee.manage")
        ser = QualificationWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tenant = _tenant(request)
        employee = _get_employee_or_404(tenant, employee_id)
        row = EmployeeQualification.objects.create(
            tenant=tenant, employee=employee, **ser.validated_data
        )
        return Response(QualificationSerializer(row).data, status=status.HTTP_201_CREATED)


class EmployeeHistoryView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view")]

    def get(self, request, employee_id):
        qs = EmploymentHistoryEvent.objects.filter(
            tenant=_tenant(request), employee_id=employee_id
        )
        return Response(HistoryEventSerializer(qs, many=True).data)


# ── Contracts ─────────────────────────────────────────────────────────────

class EmployeeContractsView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.contract.view")]

    def get(self, request, employee_id):
        service = ContractService(_tenant(request))
        return Response(ContractSerializer(service.for_employee(employee_id), many=True).data)

    def post(self, request, employee_id):
        if "hr.contract.manage" not in _held(request):
            return _forbidden("hr.contract.manage")
        ser = ContractWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        service = ContractService(_tenant(request))
        contract = service.create_contract(
            employee_id, actor=request.user, **ser.validated_data
        )
        return Response(ContractSerializer(contract).data, status=status.HTTP_201_CREATED)


class ContractOrgTableView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.contract.view")]

    def get(self, request):
        service = ContractService(_tenant(request))
        qs = service.org_table(
            status=request.query_params.get("status"),
            expiring_within=(
                int(request.query_params["expiring_within"])
                if request.query_params.get("expiring_within") else None
            ),
        )
        return _paginate(self, request, qs, ContractSerializer)


class ContractRenewView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.contract.manage")]

    def post(self, request, contract_id):
        ser = ContractRenewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        service = ContractService(_tenant(request))
        fresh = service.renew(contract_id, actor=request.user, **ser.validated_data)
        return Response(ContractSerializer(fresh).data, status=status.HTTP_201_CREATED)


class ContractDecisionView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.contract.manage")]

    def post(self, request, contract_id):
        ser = ContractDecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        service = ContractService(_tenant(request))
        contract = service.set_decision(
            contract_id, ser.validated_data["decision"], actor=request.user
        )
        return Response(ContractSerializer(contract).data)


# ── Documents ─────────────────────────────────────────────────────────────

class EmployeeDocumentsView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.document.view")]

    def get(self, request, employee_id):
        service = EmployeeDocumentService(_tenant(request))
        return Response(
            EmployeeDocumentSerializer(service.for_employee(employee_id), many=True).data
        )

    def post(self, request, employee_id):
        if "hr.document.manage" not in _held(request):
            return _forbidden("hr.document.manage")
        ser = DocumentUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        service = EmployeeDocumentService(_tenant(request))
        doc = service.add_document(employee_id, actor=request.user, **ser.validated_data)
        return Response(EmployeeDocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class EmployeeDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.document.manage")]

    def delete(self, request, document_id):
        service = EmployeeDocumentService(_tenant(request))
        service.remove_document(document_id, actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Leave ─────────────────────────────────────────────────────────────────

class HRLeaveListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.leave.view")]

    def get(self, request):
        qs = EmployeeLeave.objects.filter(tenant=_tenant(request)).select_related(
            "employee", "leave_type"
        )
        stage = request.query_params.get("stage")
        if stage == "supervisor":
            qs = qs.filter(supervisor_status="pending")
        elif stage == "hr":
            qs = qs.filter(supervisor_status="approved", hr_status="pending")
        elif request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        if request.query_params.get("employee"):
            qs = qs.filter(employee_id=request.query_params["employee"])
        return _paginate(self, request, qs.order_by("-start_date"), HRLeaveSerializer)


class LeaveSupervisorReviewView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.leave.approve")]

    def post(self, request, leave_id):
        ser = LeaveDecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        leave = LeaveService(_tenant(request)).supervisor_review(
            leave_id, _acting_employee(request),
            ser.validated_data["approve"], ser.validated_data.get("remark"),
        )
        return Response(HRLeaveSerializer(leave).data)


class LeaveHRReviewView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.leave.approve")]

    def post(self, request, leave_id):
        ser = LeaveDecisionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        leave = LeaveService(_tenant(request)).hr_review(
            leave_id, _acting_employee(request),
            ser.validated_data["approve"], ser.validated_data.get("remark"),
        )
        return Response(HRLeaveSerializer(leave).data)


class LeaveCalendarView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.leave.view")]

    def get(self, request):
        today = date.today()
        start = parse_date(request.query_params.get("from", "")) or today
        end = parse_date(request.query_params.get("to", "")) or (today + timedelta(days=30))
        rows = LeaveService(_tenant(request)).leave_calendar(
            start, end, request.query_params.get("department")
        )
        return Response({"from": start, "to": end, "entries": rows})


# ── Attendance ────────────────────────────────────────────────────────────

class AttendanceListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.attendance.manage")]

    def get(self, request):
        tenant = _tenant(request)
        today = date.today()
        start = parse_date(request.query_params.get("from", "")) or today
        end = parse_date(request.query_params.get("to", "")) or today
        qs = EmployeeAttendance.objects.filter(
            tenant=tenant, date__gte=start, date__lte=end
        ).select_related("employee")
        if request.query_params.get("employee"):
            qs = qs.filter(employee_id=request.query_params["employee"])
        return _paginate(self, request, qs.order_by("-date"), AttendanceRowSerializer)

    def post(self, request):
        ser = AttendanceMarkSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        record = AttendanceService(_tenant(request)).mark_attendance(
            str(ser.validated_data["employee_id"]),
            ser.validated_data["date"],
            ser.validated_data["status"],
            marked_by=_acting_employee(request),
            remarks=ser.validated_data.get("remarks"),
        )
        return Response(AttendanceRowSerializer(record).data, status=status.HTTP_201_CREATED)


class AttendanceAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.attendance.manage")]

    def get(self, request):
        tenant = _tenant(request)
        today = date.today()
        recorded_ids = set(
            EmployeeAttendance.objects.filter(tenant=tenant, date=today)
            .values_list("employee_id", flat=True)
        )
        no_record = Employee.objects.filter(
            tenant=tenant, status=True
        ).exclude(id__in=recorded_ids).values("id", "first_name", "last_name",
                                              "employee_number")
        return Response({
            "watchlist": hr_selectors._attendance_watchlist(tenant, today),
            "no_record_today": [
                {"id": str(r["id"]),
                 "name": f"{r['first_name']} {r['last_name']}".strip(),
                 "employee_number": r["employee_number"]}
                for r in no_record
            ],
        })


class EmployeeAttendanceView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view")]

    def get(self, request, employee_id):
        tenant = _tenant(request)
        today = date.today()
        start = parse_date(request.query_params.get("from", "")) or (today - timedelta(days=90))
        end = parse_date(request.query_params.get("to", "")) or today
        qs = EmployeeAttendance.objects.filter(
            tenant=tenant, employee_id=employee_id, date__gte=start, date__lte=end
        ).order_by("-date")
        summary = {
            "present": qs.filter(status__in=["present", "late"]).count(),
            "absent": qs.filter(status="absent").count(),
            "late": qs.filter(status="late").count(),
            "on_leave": qs.filter(status="on_leave").count(),
        }
        marked = qs.exclude(status="holiday").count()
        summary["attendance_rate"] = (
            round(summary["present"] / marked * 100, 1) if marked else None
        )
        return Response({
            "summary": summary,
            "records": AttendanceRowSerializer(qs[:200], many=True).data,
        })


# ── HR tasks ──────────────────────────────────────────────────────────────

class HRTaskListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.tasks.manage", read=["hr.employee.view"])]

    def get(self, request):
        service = HRTaskService(_tenant(request))
        qs = service.list_tasks(
            status=request.query_params.get("status"),
            category=request.query_params.get("category"),
            employee_id=request.query_params.get("employee"),
        )
        return _paginate(self, request, qs, HRTaskSerializer)

    def post(self, request):
        ser = HRTaskWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not ser.validated_data.get("title"):
            raise ValidationException("A task title is required.")
        task = HRTaskService(_tenant(request)).create_task(
            actor=request.user, **ser.validated_data
        )
        return Response(HRTaskSerializer(task).data, status=status.HTTP_201_CREATED)


class HRTaskDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.tasks.manage")]

    def patch(self, request, task_id):
        ser = HRTaskWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        task = HRTaskService(_tenant(request)).update_task(
            task_id, actor=request.user, **ser.validated_data
        )
        return Response(HRTaskSerializer(task).data)


# ── Audit ─────────────────────────────────────────────────────────────────

class AuditLogView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.employee.view")]

    def get(self, request):
        qs = HRAuditLog.objects.filter(tenant=_tenant(request))
        if request.query_params.get("target_id"):
            qs = qs.filter(target_id=request.query_params["target_id"])
        if request.query_params.get("action"):
            qs = qs.filter(action__startswith=request.query_params["action"])
        return _paginate(self, request, qs, AuditLogSerializer)


class HRAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("reports.hr")]

    def get(self, request):
        try:
            months = max(3, min(24, int(request.query_params.get("months", 12))))
        except (TypeError, ValueError):
            months = 12
        return Response(hr_selectors.hr_analytics(_tenant(request), months=months))


# ── Employee Self-Service ("My HR") ───────────────────────────────────────

class MyHRProfileView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    SELF_EDITABLE = {
        "mobile_phone", "email", "home_address_line1", "home_address_line2",
        "home_city", "emergency_contact_name", "emergency_contact_phone",
        "emergency_contact_relation", "next_of_kin_name", "next_of_kin_phone",
        "next_of_kin_relation",
    }

    def get(self, request):
        return Response(EmployeeDetailSerializer(request.employee).data)

    def patch(self, request):
        data = {k: v for k, v in request.data.items() if k in self.SELF_EDITABLE}
        for key, value in data.items():
            setattr(request.employee, key, value)
        request.employee.save(update_fields=list(data) + ["updated_at"])
        return Response(EmployeeDetailSerializer(request.employee).data)


class MyAttendanceView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def get(self, request):
        today = date.today()
        start = parse_date(request.query_params.get("from", "")) or (today - timedelta(days=90))
        qs = EmployeeAttendance.objects.filter(
            tenant=request.employee.tenant, employee=request.employee, date__gte=start
        ).order_by("-date")
        return Response(AttendanceRowSerializer(qs[:200], many=True).data)


class MyLeaveView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def get(self, request):
        qs = EmployeeLeave.objects.filter(
            tenant=request.employee.tenant, employee=request.employee
        ).select_related("leave_type").order_by("-start_date")
        return Response(HRLeaveSerializer(qs, many=True).data)

    def post(self, request):
        ser = LeaveApplySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        service = LeaveService(request.employee.tenant)
        leave = service.request_leave(
            str(request.employee.id),
            str(data["leave_type_id"]) if data.get("leave_type_id") else None,
            data["start_date"], data["end_date"], data["reason"],
            user=request.user,
        )
        if data.get("document"):
            leave.document = data["document"]
            leave.document_name = getattr(data["document"], "name", "")[:255]
            leave.save(update_fields=["document", "document_name", "updated_at"])
        return Response(HRLeaveSerializer(leave).data, status=status.HTTP_201_CREATED)


class MyContractsView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def get(self, request):
        qs = EmployeeContract.objects.filter(
            tenant=request.employee.tenant, employee=request.employee
        )
        return Response(ContractSerializer(qs, many=True).data)


class MyDocumentsView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def get(self, request):
        qs = EmployeeDocument.objects.filter(
            tenant=request.employee.tenant, employee=request.employee
        )
        return Response(EmployeeDocumentSerializer(qs, many=True).data)


# ── Leave balances ───────────────────────────────────────────────────────

def _balance_row(b):
    return {
        "leave_type": b["leave_type"].name,
        "leave_type_id": str(b["leave_type"].id),
        "allocated": b["allocated"],
        "used": b["used"],
        "remaining": b["remaining"],
    }


class LeaveBalanceView(APIView):
    """Org / per-department leave-balance report for the HR leave screen."""

    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("hr.leave.view")]

    def get(self, request):
        try:
            year = int(request.query_params["year"]) if request.query_params.get("year") else None
        except (TypeError, ValueError):
            year = None
        rows = LeaveService(_tenant(request)).get_department_leave_balance_report(
            department_id=request.query_params.get("department") or None,
            year=year,
        )
        return Response([
            {
                "employee_id": str(row["employee"].id),
                "employee_name": row["employee"].full_name,
                "employee_number": row["employee"].employee_number,
                "department": getattr(row.get("department"), "name", None),
                "balances": [_balance_row(b) for b in row["balances"]],
            }
            for row in rows
        ])


class MyLeaveBalanceView(APIView):
    """The caller's own leave balance for the current year (self-service)."""

    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def get(self, request):
        from core.models import LeaveType

        tenant = request.employee.tenant
        year = date.today().year
        service = LeaveService(tenant)
        types = LeaveType.objects.filter(tenant=tenant, status=True).order_by("name")
        return Response([
            _balance_row(service.get_leave_balance(request.employee, lt, year))
            for lt in types
        ])


# ── small helpers for per-method codename checks ─────────────────────────

def _held(request):
    from .roles import hr_permissions_for
    return hr_permissions_for(request.user)


def _forbidden(codename):
    return Response(
        {"detail": f"You do not have permission for this HR action ({codename}).",
         "code": "hr_permission_denied"},
        status=status.HTTP_403_FORBIDDEN,
    )
