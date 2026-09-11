"""Payroll portal API — mounted under /api/portal/hr/payroll/ (+ /hr/me/payslips/).

Thin DRF wrappers over :mod:`core.services.payroll_service`. HR management
endpoints require ``hr.payroll.view`` (read) / ``hr.payroll.manage`` (write); the
self-service ``/hr/me/payslips/`` endpoints only require a linked employee and
are scoped to the caller's own payslips.
"""
from __future__ import annotations

from datetime import date

from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    EmployeePayrollProfile, Payslip, PayslipLineItem, PayslipSettings,
)
from core.services.exceptions import ValidationException
from core.services.payroll_service import PayrollLookupService, PayslipService

from .hr_views import (
    HRPagination, _forbidden, _get_employee_or_404, _held, _paginate, _tenant,
)
from .permissions import HasHRPermission, IsHR, IsLinkedEmployee

_MANAGE = "hr.payroll.manage"
_VIEW = "hr.payroll.view"


# ── serialisation helpers ────────────────────────────────────────────────

def _payslip_row(p: Payslip) -> dict:
    return {
        "id": str(p.id),
        "employee_id": str(p.employee_id),
        "employee_name": p.employee.full_name,
        "employee_number": p.employee.employee_number,
        "payroll_group": p.payroll_group_name_snapshot,
        "period_start": p.period_start,
        "period_end": p.period_end,
        "gross_earnings": p.gross_earnings,
        "total_deductions": p.total_deductions,
        "net_pay": p.net_pay,
        "status": p.status,
        "version": p.version,
    }


def _payslip_detail(p: Payslip) -> dict:
    return {
        **_payslip_row(p),
        "basic_pay": p.basic_pay_snapshot,
        "rejection_reason": p.rejection_reason,
        "generated_at": p.generated_at,
        "approved_at": p.approved_at,
        "paid_at": p.paid_at,
        "line_items": [
            {
                "id": str(li.id),
                "name": li.category_name_snapshot,
                "type": li.category_type_snapshot,
                "amount": li.amount,
                "order": li.order,
            }
            for li in p.line_items.all().order_by("order")
        ],
    }


_CATEGORY_FIELDS = (
    "name", "code", "category_type", "calculation_type", "default_amount",
    "default_percentage", "is_basic_pay", "taxable", "status",
)
_GROUP_FIELDS = ("name", "description", "status")


def _lookup_row(instance, fields) -> dict:
    out = {"id": str(instance.id)}
    for f in fields:
        out[f] = getattr(instance, f, None)
    return out


# ── Payslips ─────────────────────────────────────────────────────────────

class PayslipListView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE, read=[_VIEW])]

    def get(self, request):
        qs = Payslip.objects.filter(tenant=_tenant(request)).select_related(
            "employee"
        ).order_by("-period_start", "employee__first_name")
        p = request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("employee"):
            qs = qs.filter(employee_id=p["employee"])
        if p.get("payroll_group"):
            qs = qs.filter(payroll_group_id=p["payroll_group"])
        if p.get("period_start"):
            qs = qs.filter(period_start__gte=parse_date(p["period_start"]))
        if p.get("period_end"):
            qs = qs.filter(period_end__lte=parse_date(p["period_end"]))
        return _paginate(self, request, qs, _RowSerializer)


class PayslipDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE, read=[_VIEW])]

    def get(self, request, payslip_id):
        p = Payslip.objects.select_related("employee").prefetch_related(
            "line_items"
        ).get(id=payslip_id, tenant=_tenant(request))
        return Response(_payslip_detail(p))


class PayslipGenerateView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE)]

    def post(self, request):
        tenant = _tenant(request)
        data = request.data
        start = parse_date(str(data.get("period_start", "")))
        end = parse_date(str(data.get("period_end", "")))
        if not start or not end:
            raise ValidationException("period_start and period_end are required (YYYY-MM-DD).")
        service = PayslipService(tenant)
        if data.get("payroll_group_id"):
            payslips, errors = service.generate_payslips_for_group(
                data["payroll_group_id"], start, end, generated_by=request.user
            )
            return Response(
                {"created": [_payslip_row(p) for p in payslips], "errors": errors},
                status=status.HTTP_201_CREATED,
            )
        if not data.get("employee_id"):
            raise ValidationException("Provide employee_id or payroll_group_id.")
        payslip = service.generate_payslip(
            data["employee_id"], start, end, generated_by=request.user
        )
        return Response(_payslip_detail(payslip), status=status.HTTP_201_CREATED)


class PayslipActionView(APIView):
    """POST /hr/payroll/payslips/<id>/<action>/ — approve | reject | regenerate | mark-paid | unmark-paid."""

    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE)]

    def post(self, request, payslip_id, action):
        service = PayslipService(_tenant(request))
        if action == "approve":
            p = service.approve_payslip(payslip_id, approved_by=request.user, user=request.user)
        elif action == "reject":
            reason = request.data.get("reason", "")
            if not reason:
                raise ValidationException("A rejection reason is required.")
            p = service.reject_payslip(payslip_id, reason, user=request.user)
        elif action == "regenerate":
            p = service.regenerate_payslip(payslip_id, generated_by=request.user)
        elif action == "mark-paid":
            p = service.mark_paid(payslip_id, user=request.user)
        elif action == "unmark-paid":
            p = service.unmark_paid(payslip_id, user=request.user)
        else:
            raise ValidationException(f"Unknown payslip action '{action}'.")
        return Response(_payslip_detail(p))


# ── Payroll lookups (categories + groups) ────────────────────────────────

class PayrollCategoryView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE, read=[_VIEW])]

    def get(self, request):
        rows = PayrollLookupService(_tenant(request)).list("payroll_category")
        return Response([_lookup_row(r, _CATEGORY_FIELDS) for r in rows])

    def post(self, request):
        if _MANAGE not in _held(request):
            return _forbidden(_MANAGE)
        data = {k: v for k, v in request.data.items() if k in _CATEGORY_FIELDS}
        row = PayrollLookupService(_tenant(request)).create(
            "payroll_category", user=request.user, **data
        )
        return Response(_lookup_row(row, _CATEGORY_FIELDS), status=status.HTTP_201_CREATED)


class PayrollCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE)]

    def patch(self, request, pk):
        data = {k: v for k, v in request.data.items() if k in _CATEGORY_FIELDS}
        row = PayrollLookupService(_tenant(request)).update(
            "payroll_category", pk, user=request.user, **data
        )
        return Response(_lookup_row(row, _CATEGORY_FIELDS))

    def delete(self, request, pk):
        PayrollLookupService(_tenant(request)).delete("payroll_category", pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PayrollGroupView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE, read=[_VIEW])]

    def get(self, request):
        service = PayrollLookupService(_tenant(request))
        rows = service.list("payroll_group")
        out = []
        for g in rows:
            comps = service.get_group_components(g.id)
            out.append({
                **_lookup_row(g, _GROUP_FIELDS),
                "components": [
                    {
                        "id": str(c.id),
                        "payroll_category_id": str(c.payroll_category_id),
                        "category_name": c.payroll_category.name,
                        "category_type": c.payroll_category.category_type,
                        "override_amount": c.override_amount,
                        "override_percentage": c.override_percentage,
                        "is_active": c.is_active,
                        "order": c.order,
                    }
                    for c in comps
                ],
            })
        return Response(out)

    def post(self, request):
        if _MANAGE not in _held(request):
            return _forbidden(_MANAGE)
        data = {k: v for k, v in request.data.items() if k in _GROUP_FIELDS}
        row = PayrollLookupService(_tenant(request)).create(
            "payroll_group", user=request.user, **data
        )
        return Response(_lookup_row(row, _GROUP_FIELDS), status=status.HTTP_201_CREATED)


class PayrollGroupDetailView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE)]

    def patch(self, request, pk):
        data = {k: v for k, v in request.data.items() if k in _GROUP_FIELDS}
        row = PayrollLookupService(_tenant(request)).update(
            "payroll_group", pk, user=request.user, **data
        )
        return Response(_lookup_row(row, _GROUP_FIELDS))

    def delete(self, request, pk):
        PayrollLookupService(_tenant(request)).delete("payroll_group", pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PayrollGroupComponentView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE)]

    def post(self, request, pk):
        c = PayrollLookupService(_tenant(request)).add_component_to_group(
            pk, request.data.get("payroll_category_id"), user=request.user,
            override_amount=request.data.get("override_amount"),
            override_percentage=request.data.get("override_percentage"),
        )
        return Response({"id": str(c.id)}, status=status.HTTP_201_CREATED)

    def delete(self, request, pk, component_id):
        PayrollLookupService(_tenant(request)).remove_component_from_group(component_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Payslip settings ─────────────────────────────────────────────────────

_SETTINGS_FIELDS = (
    "show_company_logo", "show_bank_details", "show_leave_balance",
    "show_ytd_earnings", "show_employee_photo", "footer_text",
)


class PayslipSettingsView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE, read=[_VIEW])]

    def get(self, request):
        s = PayslipSettings.get_settings(_tenant(request))
        return Response(_lookup_row(s, _SETTINGS_FIELDS))

    def patch(self, request):
        if _MANAGE not in _held(request):
            return _forbidden(_MANAGE)
        s = PayslipSettings.get_settings(_tenant(request))
        for k in _SETTINGS_FIELDS:
            if k in request.data:
                setattr(s, k, request.data[k])
        s.save()
        return Response(_lookup_row(s, _SETTINGS_FIELDS))


# ── Per-employee payroll profile + payslips ─────────────────────────────

_PROFILE_FIELDS = (
    "payroll_group_id", "basic_pay_amount", "bank_name",
    "bank_account_number", "bank_branch", "effective_date", "status",
)


class EmployeePayrollView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission(_MANAGE, read=[_VIEW])]

    def get(self, request, employee_id):
        tenant = _tenant(request)
        emp = _get_employee_or_404(tenant, employee_id)
        profile = EmployeePayrollProfile.objects.filter(
            tenant=tenant, employee=emp
        ).first()
        payslips = Payslip.objects.filter(tenant=tenant, employee=emp).order_by(
            "-period_start"
        )
        return Response({
            "profile": _lookup_row(profile, _PROFILE_FIELDS) if profile else None,
            "payslips": [_payslip_row(p) for p in payslips.select_related("employee")],
        })

    def patch(self, request, employee_id):
        if _MANAGE not in _held(request):
            return _forbidden(_MANAGE)
        tenant = _tenant(request)
        emp = _get_employee_or_404(tenant, employee_id)
        data = {k: v for k, v in request.data.items() if k in _PROFILE_FIELDS}
        profile, _ = EmployeePayrollProfile.objects.update_or_create(
            tenant=tenant, employee=emp, defaults=data,
        )
        return Response(_lookup_row(profile, _PROFILE_FIELDS))


# ── Self-service ─────────────────────────────────────────────────────────

class MyPayslipsView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def get(self, request):
        qs = Payslip.objects.filter(
            tenant=request.employee.tenant, employee=request.employee,
        ).exclude(status="rejected").select_related("employee").order_by("-period_start")
        return Response([_payslip_row(p) for p in qs])


class MyPayslipDetailView(APIView):
    permission_classes = [IsAuthenticated, IsLinkedEmployee]

    def get(self, request, payslip_id):
        p = Payslip.objects.select_related("employee").prefetch_related("line_items").get(
            id=payslip_id, tenant=request.employee.tenant, employee=request.employee,
        )
        return Response(_payslip_detail(p))


# ── tiny serializer shim so _paginate() can render rows ─────────────────

class _RowSerializer:
    """Duck-typed to what ``_paginate`` needs: ``cls(page, many=True).data``."""

    def __init__(self, instance, many=False, **kwargs):
        self._data = [_payslip_row(p) for p in instance] if many else _payslip_row(instance)

    @property
    def data(self):
        return self._data
