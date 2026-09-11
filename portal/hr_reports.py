"""HR reports — one endpoint, many report slugs, three render formats.

A report builder is ``fn(tenant, params) -> {"title", "columns", "rows"}`` where
``columns`` is a list of ``(key, label)`` and each row is a dict keyed by those
keys. The view turns that into JSON, CSV (opens in Excel) or PDF.

Adding a report = add a function and register it in ``REPORTS``. No view changes.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from django.http import HttpResponse
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import (
    Employee, EmployeeAttendance, EmployeeContract, EmployeeLeave, LeaveType,
)
from core.services.leave_attendance_service import LeaveService

from .permissions import HasHRPermission, IsHR


# ── builders ───────────────────────────────────────────────────────────────

def _range(params, default_days=30):
    today = date.today()
    start = parse_date(params.get("from", "")) or (today - timedelta(days=default_days))
    end = parse_date(params.get("to", "")) or today
    return start, end


def workforce(tenant, params):
    qs = Employee.objects.filter(tenant=tenant, status=True).select_related(
        "employee_department", "employee_position"
    ).order_by("employee_department__name", "first_name", "last_name")
    if params.get("staff_type") == "teaching":
        qs = qs.filter(is_teaching_staff=True)
    elif params.get("staff_type") == "non_teaching":
        qs = qs.filter(is_teaching_staff=False)
    rows = [{
        "employee_number": e.employee_number,
        "name": e.full_name,
        "department": getattr(e.employee_department, "name", ""),
        "position": getattr(e.employee_position, "name", "") or e.job_title or "",
        "type": "Teaching" if e.is_teaching_staff else "Non-teaching",
        "employment_status": e.get_employment_status_display(),
        "joining_date": e.joining_date.isoformat() if e.joining_date else "",
    } for e in qs]
    return {
        "title": "Active Employees",
        "columns": [
            ("employee_number", "Emp No"), ("name", "Name"),
            ("department", "Department"), ("position", "Position"),
            ("type", "Type"), ("employment_status", "Status"),
            ("joining_date", "Joined"),
        ],
        "rows": rows,
    }


def headcount_by_department(tenant, params):
    from django.db.models import Count
    agg = (
        Employee.objects.filter(tenant=tenant, status=True)
        .values("employee_department__name")
        .annotate(total=Count("id"))
        .order_by("employee_department__name")
    )
    rows = [{
        "department": r["employee_department__name"] or "— Unassigned —",
        "headcount": r["total"],
    } for r in agg]
    return {
        "title": "Headcount by Department",
        "columns": [("department", "Department"), ("headcount", "Headcount")],
        "rows": rows,
    }


def new_hires(tenant, params):
    start, end = _range(params, default_days=90)
    qs = Employee.objects.filter(
        tenant=tenant, joining_date__gte=start, joining_date__lte=end
    ).order_by("joining_date")
    rows = [{
        "employee_number": e.employee_number,
        "name": e.full_name,
        "department": getattr(e.employee_department, "name", ""),
        "joining_date": e.joining_date.isoformat(),
    } for e in qs]
    return {
        "title": f"New Hires ({start} to {end})",
        "columns": [
            ("employee_number", "Emp No"), ("name", "Name"),
            ("department", "Department"), ("joining_date", "Joined"),
        ],
        "rows": rows,
    }


def contracts(tenant, params):
    qs = EmployeeContract.objects.filter(tenant=tenant).select_related("employee").order_by("end_date")
    if params.get("status"):
        qs = qs.filter(renewal_status=params["status"])
    today = date.today()
    rows = [{
        "employee_number": c.employee.employee_number,
        "name": c.employee.full_name,
        "contract_type": c.get_contract_type_display(),
        "start_date": c.start_date.isoformat(),
        "end_date": c.end_date.isoformat() if c.end_date else "—",
        "days_remaining": (c.end_date - today).days if c.end_date else "",
        "renewal_status": c.get_renewal_status_display(),
    } for c in qs]
    return {
        "title": "Contracts",
        "columns": [
            ("employee_number", "Emp No"), ("name", "Name"),
            ("contract_type", "Type"), ("start_date", "Start"),
            ("end_date", "End"), ("days_remaining", "Days Left"),
            ("renewal_status", "Renewal Status"),
        ],
        "rows": rows,
    }


def probation(tenant, params):
    qs = Employee.objects.filter(
        tenant=tenant, status=True, employment_status="probation"
    ).order_by("first_name", "last_name")
    rows = [{
        "employee_number": e.employee_number,
        "name": e.full_name,
        "department": getattr(e.employee_department, "name", ""),
        "joining_date": e.joining_date.isoformat() if e.joining_date else "",
        "probation_end": (
            e.current_contract.probation_end_date.isoformat()
            if e.current_contract and e.current_contract.probation_end_date else ""
        ),
    } for e in qs]
    return {
        "title": "Employees on Probation",
        "columns": [
            ("employee_number", "Emp No"), ("name", "Name"),
            ("department", "Department"), ("joining_date", "Joined"),
            ("probation_end", "Probation Ends"),
        ],
        "rows": rows,
    }


def attendance(tenant, params):
    start, end = _range(params)
    employees = Employee.objects.filter(tenant=tenant, status=True).order_by(
        "employee_department__name", "first_name"
    )
    rows = []
    for e in employees:
        recs = EmployeeAttendance.objects.filter(
            tenant=tenant, employee=e, date__gte=start, date__lte=end
        )
        present = recs.filter(status__in=["present", "late"]).count()
        marked = recs.exclude(status="holiday").count()
        rows.append({
            "employee_number": e.employee_number,
            "name": e.full_name,
            "present": present,
            "absent": recs.filter(status="absent").count(),
            "late": recs.filter(status="late").count(),
            "on_leave": recs.filter(status="on_leave").count(),
            "percentage": round(present / marked * 100, 1) if marked else "",
        })
    return {
        "title": f"Staff Attendance ({start} to {end})",
        "columns": [
            ("employee_number", "Emp No"), ("name", "Name"),
            ("present", "Present"), ("absent", "Absent"), ("late", "Late"),
            ("on_leave", "On Leave"), ("percentage", "%"),
        ],
        "rows": rows,
    }


def leave_taken(tenant, params):
    start, end = _range(params, default_days=90)
    qs = EmployeeLeave.objects.filter(
        tenant=tenant, status="approved", start_date__lte=end, end_date__gte=start
    ).select_related("employee", "leave_type").order_by("start_date")
    rows = [{
        "employee_number": lv.employee.employee_number,
        "name": lv.employee.full_name,
        "leave_type": getattr(lv.leave_type, "name", lv.leave_type_legacy or "Leave"),
        "start_date": lv.start_date.isoformat(),
        "end_date": lv.end_date.isoformat(),
        "days": (lv.end_date - lv.start_date).days + 1,
    } for lv in qs]
    return {
        "title": f"Leave Taken ({start} to {end})",
        "columns": [
            ("employee_number", "Emp No"), ("name", "Name"),
            ("leave_type", "Leave Type"), ("start_date", "From"),
            ("end_date", "To"), ("days", "Days"),
        ],
        "rows": rows,
    }


def leave_balances(tenant, params):
    year = int(params.get("year") or date.today().year)
    service = LeaveService(tenant)
    report = service.get_department_leave_balance_report(
        department_id=params.get("department"), year=year
    )
    types = list(LeaveType.objects.filter(tenant=tenant, status=True))
    columns = [("employee_number", "Emp No"), ("name", "Name")]
    columns += [(f"lt_{lt.id}", lt.name) for lt in types]
    rows = []
    for entry in report:
        e = entry["employee"]
        row = {"employee_number": e.employee_number, "name": e.full_name}
        for lt, bal in zip(types, entry["balances"]):
            row[f"lt_{lt.id}"] = bal["remaining"]
        rows.append(row)
    return {"title": f"Leave Balances {year}", "columns": columns, "rows": rows}


REPORTS = {
    "workforce": (workforce, "reports.hr"),
    "headcount-by-department": (headcount_by_department, "reports.hr"),
    "new-hires": (new_hires, "reports.hr"),
    "contracts": (contracts, "reports.hr"),
    "probation": (probation, "reports.hr"),
    "attendance": (attendance, "reports.hr"),
    "leave-taken": (leave_taken, "reports.hr"),
    "leave-balances": (leave_balances, "reports.hr"),
}


# ── rendering ──────────────────────────────────────────────────────────────

def _csv_response(report):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for _, label in report["columns"]])
    for row in report["rows"]:
        writer.writerow([row.get(key, "") for key, _ in report["columns"]])
    resp = HttpResponse(buf.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{report["title"]}.csv"'
    return resp


def _pdf_response(report):
    from weasyprint import HTML

    head = "".join(f"<th>{label}</th>" for _, label in report["columns"])
    body = "".join(
        "<tr>" + "".join(
            f"<td>{row.get(key, '')}</td>" for key, _ in report["columns"]
        ) + "</tr>"
        for row in report["rows"]
    )
    html = f"""
    <html><head><style>
      body {{ font-family: sans-serif; font-size: 11px; }}
      h1 {{ font-size: 16px; }}
      table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #999; padding: 4px 6px; text-align: left; }}
      th {{ background: #eee; }}
    </style></head><body>
      <h1>{report['title']}</h1>
      <p>Generated {date.today():%d %b %Y} · {len(report['rows'])} rows</p>
      <table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
    </body></html>
    """
    pdf = HTML(string=html).write_pdf()
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{report["title"]}.pdf"'
    return resp


class HRReportView(APIView):
    """GET /api/portal/hr/reports/<slug>/?format=json|csv|pdf & report params."""

    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("reports.hr")]

    def get(self, request, slug):
        entry = REPORTS.get(slug)
        if not entry:
            return Response({"detail": f"Unknown report '{slug}'."}, status=404)
        builder, _codename = entry
        tenant = getattr(request, "tenant", None) or request.role_set.employee.tenant
        report = builder(tenant, request.query_params)

        fmt = request.query_params.get("format", "json").lower()
        if fmt in ("csv", "xlsx", "excel"):
            return _csv_response(report)
        if fmt == "pdf":
            if "reports.hr.export" not in _held(request):
                return Response({"detail": "Missing reports.hr.export."}, status=403)
            return _pdf_response(report)
        return Response(report)


class HRReportIndexView(APIView):
    permission_classes = [IsAuthenticated, IsHR, HasHRPermission("reports.hr")]

    def get(self, request):
        return Response({
            "reports": [
                {"slug": slug, "title": fn.__doc__ or slug.replace("-", " ").title()}
                for slug, (fn, _c) in REPORTS.items()
            ]
        })


def _held(request):
    from .roles import hr_permissions_for
    return hr_permissions_for(request.user)
