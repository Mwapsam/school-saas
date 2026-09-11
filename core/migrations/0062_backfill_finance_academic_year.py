# Backfill academic_year on the consolidated finance ledger (Phase 1).
#
# Idempotent and re-runnable: only rows where academic_year_id IS NULL are
# touched, so re-running (or running after new rows were inserted with a null
# year) is safe. Resolution order per row:
#   1. the AcademicYear whose [start_date, end_date] contains the row's date
#   2. the student's enrolled batch academic year (BatchStudent -> Batch)
#   3. the tenant's active AcademicYear (is_active=True)
# Rows that still can't be resolved (e.g. tenant has no AcademicYear at all)
# are left null and reported, to be reviewed before the FK is made required.
from django.db import migrations


def _load_years_by_tenant(AcademicYear):
    """tenant_id -> list of (id, start_date, end_date) ordered by start_date."""
    years = {}
    for ay in AcademicYear.objects.all().values(
        "id", "tenant_id", "start_date", "end_date"
    ):
        years.setdefault(ay["tenant_id"], []).append(
            (ay["id"], ay["start_date"], ay["end_date"])
        )
    for rows in years.values():
        rows.sort(key=lambda r: r[1] or r[0])
    return years


def _load_active_year_by_tenant(AcademicYear):
    """tenant_id -> active AcademicYear id."""
    active = {}
    for ay in AcademicYear.objects.filter(is_active=True).values("id", "tenant_id"):
        active.setdefault(ay["tenant_id"], ay["id"])
    return active


def _load_student_year_map(BatchStudent):
    """student_id -> academic_year_id from the student's batch enrollment.

    Prefer active enrollments and the most recent academic year start_date.
    """
    best = {}  # student_id -> (is_active, start_date, academic_year_id)
    rows = BatchStudent.objects.exclude(
        batch__academic_year_id__isnull=True
    ).values(
        "student_id",
        "batch__academic_year_id",
        "batch__academic_year__start_date",
        "is_active",
    )
    for r in rows:
        sid = r["student_id"]
        key = (
            1 if r["is_active"] else 0,
            r["batch__academic_year__start_date"],
        )
        current = best.get(sid)
        if current is None or key > current[0]:
            best[sid] = (key, r["batch__academic_year_id"])
    return {sid: v[1] for sid, v in best.items()}


def _year_for_date(years_for_tenant, d):
    if not d or not years_for_tenant:
        return None
    for ay_id, start, end in years_for_tenant:
        if start and end and start <= d <= end:
            return ay_id
    return None


def _backfill_model(model, date_attrs, years_by_tenant, active_by_tenant,
                    student_year_map, has_student):
    """Return (updated, unresolved) counts. Only fills null academic_year_id.

    ``date_attrs`` is tried in order; the first non-null value is used for
    date-range matching (e.g. transaction_date, then created_at).
    """
    updated = 0
    unresolved = 0
    to_update = []
    qs = model.objects.filter(academic_year_id__isnull=True)
    for obj in qs.iterator(chunk_size=2000):
        d = None
        for attr in date_attrs:
            d = getattr(obj, attr, None)
            if d is not None:
                break
        # Datetimes (e.g. FeeTransaction.transaction_date) normalise to date.
        if d is not None and hasattr(d, "date"):
            d = d.date()

        ay_id = _year_for_date(years_by_tenant.get(obj.tenant_id, []), d)

        if ay_id is None and has_student:
            ay_id = student_year_map.get(obj.student_id)

        if ay_id is None:
            ay_id = active_by_tenant.get(obj.tenant_id)

        if ay_id is None:
            unresolved += 1
            continue

        obj.academic_year_id = ay_id
        to_update.append(obj)
        if len(to_update) >= 1000:
            model.objects.bulk_update(to_update, ["academic_year_id"])
            updated += len(to_update)
            to_update = []

    if to_update:
        model.objects.bulk_update(to_update, ["academic_year_id"])
        updated += len(to_update)

    return updated, unresolved


def forwards(apps, schema_editor):
    AcademicYear = apps.get_model("core", "AcademicYear")
    BatchStudent = apps.get_model("core", "BatchStudent")
    FinanceFee = apps.get_model("core", "FinanceFee")
    FinanceTransaction = apps.get_model("core", "FinanceTransaction")
    FeeTransaction = apps.get_model("core", "FeeTransaction")
    FeeCollection = apps.get_model("core", "FeeCollection")

    if not AcademicYear.objects.exists():
        # Nothing to map against (e.g. empty / non-tenant schema) — no-op.
        return

    years_by_tenant = _load_years_by_tenant(AcademicYear)
    active_by_tenant = _load_active_year_by_tenant(AcademicYear)
    student_year_map = _load_student_year_map(BatchStudent)

    targets = [
        (FinanceFee, ("transaction_date", "created_at"), True),
        (FinanceTransaction, ("transaction_date", "created_at"), True),
        (FeeTransaction, ("transaction_date", "created_at"), True),
        (FeeCollection, ("start_date", "due_date"), False),
    ]

    total_unresolved = 0
    for model, date_attrs, has_student in targets:
        updated, unresolved = _backfill_model(
            model, date_attrs, years_by_tenant, active_by_tenant,
            student_year_map, has_student,
        )
        total_unresolved += unresolved
        print(
            f"  {model.__name__}: backfilled academic_year on {updated} row(s)"
            + (f", {unresolved} unresolved (left null)" if unresolved else "")
        )

    # Rows that match no year by date, have no student enrollment, and whose
    # tenant has no active year (e.g. some employee/expense rows) remain null
    # by design and are reported for manual review.
    if total_unresolved:
        print(
            f"  NOTE: {total_unresolved} finance row(s) could not be mapped to "
            "an academic year and were left null for manual review."
        )


def backwards(apps, schema_editor):
    # Non-destructive: backfilled values are indistinguishable from manually
    # set ones, so we do not null them out on reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0061_add_academic_year_to_finance_models"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
