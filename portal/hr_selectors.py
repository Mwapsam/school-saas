"""Read-only aggregation for the HR portal (dashboard + alert lists).

Everything here takes a ``tenant`` and returns plain dicts/lists — no request,
no serializers — so it can be reused by reports, the nightly job, or tests.
Metrics that need modules not yet built (recruitment, performance, training,
onboarding, exit) are returned as ``None`` so the frontend can hide those cards.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, Q

from core.models import (
    Employee, EmployeeAttendance, EmployeeContract, EmployeeDocument,
    EmployeeExit, EmployeeLeave, HRTask, OnboardingChecklist, PerformanceReview,
    TrainingRecord,
)


def _today():
    return date.today()


def hr_dashboard(tenant) -> dict:
    today = _today()
    emp = Employee.objects.filter(tenant=tenant)
    active = emp.filter(status=True)

    att_today = EmployeeAttendance.objects.filter(tenant=tenant, date=today)
    present_today = att_today.filter(status__in=["present", "late"]).count()
    absent_today = att_today.filter(status="absent").count()

    on_leave = EmployeeLeave.objects.filter(
        tenant=tenant, status="approved",
        start_date__lte=today, end_date__gte=today,
    ).values("employee_id").distinct().count()

    pending_leave = EmployeeLeave.objects.filter(
        tenant=tenant,
    ).filter(Q(status="pending") | Q(supervisor_status="pending") | Q(hr_status="pending")).exclude(
        status__in=["approved", "rejected"]
    ).count()

    term_start = today - timedelta(days=120)  # ~one school term; refine when Term wired

    cards = {
        "total_active": active.count(),
        "teaching_staff": active.filter(is_teaching_staff=True).count(),
        "non_teaching_staff": active.filter(is_teaching_staff=False).count(),
        "present_today": present_today,
        "absent_today": absent_today,
        "on_leave": on_leave,
        "on_probation": active.filter(employment_status="probation").count(),
        "notice_period": active.filter(employment_status="notice_period").count(),
        "contracts_expiring_soon": EmployeeContract.objects.filter(
            tenant=tenant, end_date__isnull=False,
            end_date__gte=today, end_date__lte=today + timedelta(days=90),
        ).exclude(renewal_status__in=["renewed", "not_renewed"]).count(),
        "new_this_term": active.filter(joining_date__gte=term_start).count(),
        "pending_leave_requests": pending_leave,
        "pending_hr_tasks": HRTask.objects.filter(
            tenant=tenant, status__in=["pending", "in_progress"]
        ).count(),
        "onboarding_in_progress": OnboardingChecklist.objects.filter(
            tenant=tenant, completed_at__isnull=True
        ).count(),
        "appraisals_due": PerformanceReview.objects.filter(
            tenant=tenant, review_date__lte=today
        ).exclude(status="completed").count(),
        "mandatory_training_gaps": _mandatory_training_gap_count(tenant),
        "employees_exiting": EmployeeExit.objects.filter(
            tenant=tenant, status="in_progress"
        ).count(),
    }

    alerts = {
        "contracts_expiring": _contracts_expiring(tenant, today),
        "probation_reviews_due": _probation_due(tenant, today),
        "documents_missing": _documents_missing(tenant),
        "appraisals_due": _appraisals_due(tenant, today),
        "documents_expiring": _documents_expiring(tenant, today),
        "pending_leave_approvals": _pending_leave(tenant),
        "attendance_watchlist": _attendance_watchlist(tenant, today),
        "open_tasks": _open_tasks(tenant),
        "onboarding_outstanding": _onboarding_outstanding(tenant),
        "training_expiring": _training_expiring(tenant, today),
        "exit_clearance_outstanding": _exit_outstanding(tenant),
    }
    return {"cards": cards, "alerts": alerts, "generated_at": today.isoformat()}


def _exit_outstanding(tenant, limit=20):
    rows = []
    qs = (
        EmployeeExit.objects.filter(tenant=tenant, status="in_progress")
        .select_related("employee")
        .prefetch_related("clearance_items")[:limit]
    )
    for ex in qs:
        p = ex.clearance_progress()
        rows.append({
            **_emp_row(ex.employee),
            "exit_id": str(ex.id),
            "exit_type": ex.exit_type,
            "last_working_date": ex.last_working_date.isoformat() if ex.last_working_date else None,
            "percent": p["percent"],
        })
    return rows


def _mandatory_training_gap_count(tenant) -> int:
    from core.services.hr_training_service import TrainingService
    try:
        return len(TrainingService(tenant).mandatory_gaps())
    except Exception:
        return 0


def _training_expiring(tenant, today, within=60):
    horizon = today + timedelta(days=within)
    rows = []
    qs = TrainingRecord.objects.filter(
        tenant=tenant, status="completed",
        expiry_date__isnull=False, expiry_date__lte=horizon,
    ).select_related("employee").order_by("expiry_date")[:30]
    for t in qs:
        rows.append({
            **_emp_row(t.employee),
            "training": t.name,
            "expiry_date": t.expiry_date.isoformat(),
            "mandatory": t.is_mandatory,
        })
    return rows


def _onboarding_outstanding(tenant, limit=20):
    rows = []
    qs = (
        OnboardingChecklist.objects.filter(tenant=tenant, completed_at__isnull=True)
        .select_related("employee")
        .prefetch_related("items")[:limit]
    )
    for cl in qs:
        p = cl.progress()
        rows.append({
            **_emp_row(cl.employee),
            "checklist_id": str(cl.id),
            "percent": p["percent"],
            "done": p["done"],
            "total": p["total"],
        })
    return rows


def _emp_row(e: Employee) -> dict:
    return {
        "id": str(e.id),
        "name": e.full_name,
        "employee_number": e.employee_number,
        "department": getattr(e.employee_department, "name", None),
    }


def _appraisals_due(tenant, today, limit=20):
    """Reviews whose review_date has passed but are not yet completed, plus
    active employees whose last completed review's next_review_date is past."""
    rows = []
    qs = (
        PerformanceReview.objects.filter(tenant=tenant, review_date__lte=today)
        .exclude(status="completed")
        .select_related("employee", "employee__employee_department")
        .order_by("review_date")[:limit]
    )
    for r in qs:
        rows.append({
            **_emp_row(r.employee),
            "review_id": str(r.id),
            "review_period": r.review_period,
            "review_date": r.review_date.isoformat() if r.review_date else None,
            "status": r.status,
        })
    return rows


def _documents_missing(tenant, limit=50):
    """Active employees who are missing one or more of the tenant's required
    document types (configured under HR Settings → document types)."""
    from .hr_settings_views import required_document_types

    required = required_document_types(tenant)
    if not required:
        return []
    required_lower = {r.lower(): r for r in required}
    rows = []
    employees = Employee.objects.filter(tenant=tenant, status=True).select_related(
        "employee_department"
    )
    held = {}
    for emp_id, dtype in EmployeeDocument.objects.filter(
        tenant=tenant, document_type__isnull=False
    ).values_list("employee_id", "document_type"):
        held.setdefault(emp_id, set()).add((dtype or "").strip().lower())
    for e in employees:
        have = held.get(e.id, set())
        missing = [label for key, label in required_lower.items() if key not in have]
        if missing:
            rows.append({**_emp_row(e), "missing": missing})
        if len(rows) >= limit:
            break
    return rows


def _contracts_expiring(tenant, today, windows=(90, 60, 30)):
    horizon = today + timedelta(days=windows[0])
    rows = []
    qs = EmployeeContract.objects.filter(
        tenant=tenant, end_date__isnull=False,
        end_date__gte=today, end_date__lte=horizon,
    ).exclude(renewal_status__in=["renewed", "not_renewed"]).select_related("employee")
    for c in qs.order_by("end_date"):
        rows.append({
            **_emp_row(c.employee),
            "contract_id": str(c.id),
            "end_date": c.end_date.isoformat(),
            "days_remaining": (c.end_date - today).days,
        })
    return rows


def _probation_due(tenant, today, within=30):
    horizon = today + timedelta(days=within)
    rows = []
    qs = EmployeeContract.objects.filter(
        tenant=tenant, probation_end_date__isnull=False,
        probation_end_date__gte=today, probation_end_date__lte=horizon,
    ).select_related("employee")
    for c in qs.order_by("probation_end_date"):
        rows.append({
            **_emp_row(c.employee),
            "probation_end_date": c.probation_end_date.isoformat(),
        })
    return rows


def _documents_expiring(tenant, today, within=60):
    horizon = today + timedelta(days=within)
    rows = []
    qs = EmployeeDocument.objects.filter(
        tenant=tenant, expiry_date__isnull=False, expiry_date__lte=horizon,
    ).select_related("employee")
    for d in qs.order_by("expiry_date"):
        rows.append({
            **_emp_row(d.employee),
            "document_id": str(d.id),
            "document_type": d.document_type,
            "expiry_date": d.expiry_date.isoformat(),
            "status": d.status(),
        })
    return rows


def _pending_leave(tenant):
    rows = []
    qs = EmployeeLeave.objects.filter(
        tenant=tenant,
    ).exclude(status__in=["approved", "rejected"]).select_related("employee", "leave_type")
    for lv in qs.order_by("start_date")[:100]:
        rows.append({
            **_emp_row(lv.employee),
            "leave_id": str(lv.id),
            "start_date": lv.start_date.isoformat(),
            "end_date": lv.end_date.isoformat(),
            "stage": "hr" if lv.supervisor_status == "approved" else "supervisor",
        })
    return rows


def _attendance_watchlist(tenant, today, lookback=30, late_threshold=3, absent_threshold=3):
    since = today - timedelta(days=lookback)
    agg = (
        EmployeeAttendance.objects.filter(tenant=tenant, date__gte=since)
        .values("employee_id", "employee__first_name", "employee__last_name",
                "employee__employee_number")
        .annotate(
            lates=Count("id", filter=Q(status="late")),
            absents=Count("id", filter=Q(status="absent")),
        )
        .filter(Q(lates__gte=late_threshold) | Q(absents__gte=absent_threshold))
    )
    return [
        {
            "id": str(r["employee_id"]),
            "name": f"{r['employee__first_name']} {r['employee__last_name']}".strip(),
            "employee_number": r["employee__employee_number"],
            "late_count": r["lates"],
            "absent_count": r["absents"],
        }
        for r in agg
    ]


def _open_tasks(tenant):
    rows = []
    qs = HRTask.objects.filter(
        tenant=tenant, status__in=["pending", "in_progress"]
    ).order_by("due_date")[:100]
    for t in qs:
        rows.append({
            "id": str(t.id),
            "title": t.title,
            "category": t.category,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
        })
    return rows


# ── HR analytics (Phase 3) ────────────────────────────────────────────────
def _month_starts(today, n):
    """The first day of each of the last ``n`` months, oldest first."""
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def _next_month(d):
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def hr_analytics(tenant, *, months: int = 12) -> dict:
    today = _today()
    window_start = today - timedelta(days=365)
    emp = Employee.objects.filter(tenant=tenant)
    active = emp.filter(status=True)
    active_count = active.count()
    teaching = active.filter(is_teaching_staff=True).count()

    # Turnover: completed exits in the trailing 12 months over average headcount.
    exits_qs = EmployeeExit.objects.filter(
        tenant=tenant, status="completed",
        last_working_date__gte=window_start, last_working_date__lte=today,
    )
    exits_12m = exits_qs.count()
    joiners_12m = emp.filter(
        joining_date__gte=window_start, joining_date__lte=today
    ).count()
    avg_headcount = active_count + (exits_12m - joiners_12m) / 2 or active_count
    turnover_rate = round(exits_12m / avg_headcount * 100, 1) if avg_headcount else 0.0

    # Joiners / leavers per month.
    starts = _month_starts(today, months)
    trend = []
    for ms in starts:
        me = _next_month(ms)
        trend.append({
            "month": ms.strftime("%Y-%m"),
            "joined": emp.filter(joining_date__gte=ms, joining_date__lt=me).count(),
            "left": EmployeeExit.objects.filter(
                tenant=tenant, status="completed",
                last_working_date__gte=ms, last_working_date__lt=me,
            ).count(),
        })

    # Tenure bands.
    bands = [("<1y", 0, 1), ("1-3y", 1, 3), ("3-5y", 3, 5), ("5-10y", 5, 10), ("10y+", 10, 200)]
    tenure = []
    for label, lo, hi in bands:
        hi_date = date(today.year - lo, today.month, 1)
        lo_date = date(today.year - hi, today.month, 1)
        tenure.append({
            "band": label,
            "count": active.filter(joining_date__lte=hi_date, joining_date__gt=lo_date).count(),
        })

    # Contract-type mix among the current active workforce.
    contract_mix = list(
        EmployeeContract.objects.filter(
            tenant=tenant, employee__status=True,
        )
        .exclude(renewal_status__in=["renewed", "expired"])
        .values("contract_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Approved leave days by type, trailing 12 months.
    leave_by_type: dict[str, int] = {}
    lv_qs = EmployeeLeave.objects.filter(
        tenant=tenant, status="approved", start_date__gte=window_start,
    ).select_related("leave_type")
    for lv in lv_qs:
        key = getattr(lv.leave_type, "name", None) or lv.leave_type_legacy or "Unspecified"
        leave_by_type[key] = leave_by_type.get(key, 0) + (lv.end_date - lv.start_date).days + 1
    leave_days = [{"type": k, "days": v} for k, v in
                  sorted(leave_by_type.items(), key=lambda kv: -kv[1])]

    # Attendance rate, trailing 30 days.
    att = EmployeeAttendance.objects.filter(tenant=tenant, date__gte=today - timedelta(days=30))
    att_total = att.count()
    att_present = att.filter(status__in=["present", "late", "official_duty", "training"]).count()
    attendance_rate = round(att_present / att_total * 100, 1) if att_total else None

    # Per-department headcount + trailing-12-month exits.
    dept_rows = list(
        active.values("employee_department__name")
        .annotate(headcount=Count("id"))
        .order_by("-headcount")
    )
    dept_exits: dict[str, int] = {}
    for x in exits_qs.select_related("employee__employee_department"):
        name = getattr(x.employee.employee_department, "name", None) or "Unassigned"
        dept_exits[name] = dept_exits.get(name, 0) + 1
    by_department = [
        {
            "department": r["employee_department__name"] or "Unassigned",
            "headcount": r["headcount"],
            "exits_12m": dept_exits.get(r["employee_department__name"] or "Unassigned", 0),
        }
        for r in dept_rows
    ]

    return {
        "generated_at": today.isoformat(),
        "headcount": {
            "active": active_count,
            "teaching": teaching,
            "non_teaching": active_count - teaching,
        },
        "turnover": {
            "exits_12m": exits_12m,
            "joiners_12m": joiners_12m,
            "avg_headcount": round(avg_headcount, 1),
            "turnover_rate": turnover_rate,
        },
        "trend": trend,
        "tenure": tenure,
        "contract_mix": contract_mix,
        "leave_days": leave_days,
        "attendance_rate": attendance_rate,
        "by_department": by_department,
    }
