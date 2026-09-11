"""Admin utilities for sidebar permission checks and configuration."""

import json
from datetime import timedelta

from django.db import connection
from django.db.models import Case, Count, IntegerField, Q, Sum, When
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django_tenants.utils import get_public_schema_name


# ---------------------------------------------------------------------------
# Sidebar permission helpers
# ---------------------------------------------------------------------------

def is_public_schema(request) -> bool:
    """Check if current request is in public schema (multi-tenant admin)."""
    return connection.schema_name == get_public_schema_name()


def is_tenant_schema(request) -> bool:
    """Check if current request is in a tenant schema (school admin)."""
    return connection.schema_name != get_public_schema_name()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _months_back(date_, n):
    """First-of-month date, n calendar months before date_ (n may be negative
    to step forward). No external deps (no dateutil required)."""
    month = date_.month - n
    year = date_.year
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date_.replace(year=year, month=month, day=1)


def _to_json(value):
    """json.dumps that's safe to drop straight into a <script> tag with |safe.

    Needed because Decimal/date values coming back from the ORM aren't
    JSON-serializable by default, and relying on the |safe filter on a raw
    Python list produces things like Decimal('12.50') or single-quoted
    strings, which are not valid JavaScript.
    """
    return json.dumps(value, default=float)


# ---------------------------------------------------------------------------
# Dashboard callback
# ---------------------------------------------------------------------------

def dashboard_callback(request, context):
    is_public = connection.schema_name == get_public_schema_name()
    context["is_public"] = is_public

    if not is_public:
        from core.models import (
            Student, Batch, BatchStudent, FamilyInvoice, FeeTransaction,
            FinanceFee, Attendance, QuickBooksFeeInvoiceSync,
            ExtendedAdmissionApplication, ExamGroup,
        )

        today = timezone.now().date()

        # --- KPI cards ----------------------------------------------------
        context["total_students"] = Student.objects.filter(
            is_active=True, is_deleted=False
        ).count()
        context["active_batches"] = Batch.objects.filter(
            is_active=True, is_deleted=False
        ).count()
        context["pending_admissions"] = ExtendedAdmissionApplication.objects.filter(
            status__in=["submitted", "under_review"]
        ).count()

        week_later = today + timedelta(days=7)
        context["upcoming_exams"] = ExamGroup.objects.filter(
            exam_date__gte=today,
            exam_date__lte=week_later,
            is_published=True,
        ).count()

        open_invoices = FamilyInvoice.objects.filter(status="open")
        context["open_invoices"] = open_invoices.count()
        context["outstanding_balance"] = float(
            open_invoices.aggregate(total=Sum("balance_due"))["total"] or 0
        )

        context["recent_payments"] = (
            FeeTransaction.objects.filter(transaction_type="payment")
            .select_related("student")
            .order_by("-transaction_date")[:5]
        )

        context["qb_sync_failures"] = QuickBooksFeeInvoiceSync.objects.filter(
            sync_status="failed"
        ).count()

        # --- Chart 1: monthly revenue, last 6 months (line) ----------------
        start_month = _months_back(today, 5)
        months = []
        cursor = start_month
        for _ in range(6):
            months.append(cursor)
            cursor = _months_back(cursor, -1)  # step forward one month

        revenue_qs = (
            FeeTransaction.objects.filter(
                transaction_type="payment",
                transaction_date__date__gte=start_month,
            )
            .annotate(month=TruncMonth("transaction_date"))
            .values("month")
            .annotate(total=Sum("amount"))
        )
        revenue_by_month = {}
        for row in revenue_qs:
            m = row["month"]
            key = m.date() if hasattr(m, "date") else m
            revenue_by_month[key] = row["total"]

        context["revenue_chart_labels"] = _to_json(
            [m.strftime("%b %Y") for m in months]
        )
        context["revenue_chart_data"] = _to_json(
            [float(revenue_by_month.get(m, 0) or 0) for m in months]
        )

        # --- Chart 2: outstanding balance by fee category (doughnut) -------
        category_totals = (
            FinanceFee.objects.filter(is_paid=False)
            .values("fee_category__name")
            .annotate(total=Sum("balance"))
            .order_by("-total")[:6]
        )
        context["fee_category_labels"] = _to_json(
            [row["fee_category__name"] or "Uncategorized" for row in category_totals]
        )
        context["fee_category_data"] = _to_json(
            [float(row["total"] or 0) for row in category_totals]
        )

        # --- Chart 3: daily attendance rate, last 14 days (line) -----------
        start_day = today - timedelta(days=13)
        attendance_by_day = (
            Attendance.objects.filter(month_date__gte=start_day, month_date__lte=today)
            .values("month_date")
            .annotate(
                total=Count("id"),
                present=Sum(
                    Case(
                        When(Q(forenoon=True) | Q(afternoon=True), then=1),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
            )
            .order_by("month_date")
        )
        attendance_map = {
            row["month_date"]: (row["present"] / row["total"] * 100 if row["total"] else 0)
            for row in attendance_by_day
        }
        day_range = [start_day + timedelta(days=i) for i in range(14)]
        context["attendance_chart_labels"] = _to_json(
            [d.strftime("%d %b") for d in day_range]
        )
        context["attendance_chart_data"] = _to_json(
            [round(attendance_map.get(d, 0), 1) for d in day_range]
        )

        # --- Chart 4: active students per batch, top 8 (bar) ---------------
        batch_counts = (
            BatchStudent.objects.filter(is_active=True, batch__is_active=True)
            .values("batch__name")
            .annotate(total=Count("id"))
            .order_by("-total")[:8]
        )
        context["batch_enrollment_labels"] = _to_json(
            [row["batch__name"] for row in batch_counts]
        )
        context["batch_enrollment_data"] = _to_json(
            [row["total"] for row in batch_counts]
        )

    else:
        from core.models import School, Domain

        context["total_tenants"] = School.objects.filter(is_active=True).count()
        context["total_domains"] = Domain.objects.count()
        context["recent_tenants"] = School.objects.order_by("-id")[:5]

        # --- Chart: active vs inactive schools (doughnut) ------------------
        active_count = School.objects.filter(is_active=True).count()
        inactive_count = School.objects.filter(is_active=False).count()
        context["school_status_labels"] = _to_json(["Active", "Inactive"])
        context["school_status_data"] = _to_json([active_count, inactive_count])

        # --- Chart: domains per school, top 10 (bar) ------------------------
        domain_counts = (
            Domain.objects.values("tenant__name")
            .annotate(total=Count("id"))
            .order_by("-total")[:10]
        )
        context["domains_per_school_labels"] = _to_json(
            [row["tenant__name"] for row in domain_counts]
        )
        context["domains_per_school_data"] = _to_json(
            [row["total"] for row in domain_counts]
        )

    return context
