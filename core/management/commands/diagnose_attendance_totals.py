"""
Explain where a report card's attendance total comes from.

The attendance block on a report card is **not** derived from attendance rows.
It is a pure calendar count::

    total_days = dates in [range.start .. range.end]
                 whose weekday() is in AttendanceSettings.working_days
                 and which no Event(is_holiday=True) covers

Attendance rows only ever move a day from "present" to "absent"; they cannot
change the total. So when the total is wrong, one of three calendar inputs is
wrong — the range, the working weekdays, or the holiday events — or the number
on the card is a stale `StudentReport.report_data` cache. This command names
which.

The range is per *exam group*, and an exam group belongs to one batch, so two
grades in the same school can legitimately disagree about how long a term is.
That is why the cross-batch table below is usually where the answer appears.

Rather than re-deriving any of it (which would drift), this reports straight
from `ReportGenerationService.resolve_attendance_range` and
`SchoolCalendarService` — the same code the report card runs.

Read-only. Nothing here writes.

Usage:
    # One batch, with the full dated working-day list
    python manage.py diagnose_attendance_totals --tenant=<schema> --batch=1B --list-days

    # Every batch: the cross-batch comparison and structural summary
    python manage.py diagnose_attendance_totals --tenant=<schema>
"""

import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _normalise(name: str) -> str:
    return _NON_ALNUM.sub("", (name or "").lower())


def _looks_like_uuid(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F-]{32,36}", value or ""))


def _day(d) -> str:
    """A date the way a human checking a school calendar reads it."""
    return f"{d:%Y-%m-%d} {_WEEKDAY_NAMES[d.weekday()]}"


class Command(BaseCommand):
    help = (
        "Explain a report card's attendance total: the date range it was "
        "computed over, the working days and holidays that shaped it, and "
        "how it compares with every other batch."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--batch", default=None,
                            help="Batch id, or a case-insensitive name fragment")
        parser.add_argument("--exam-group", default=None,
                            help="Exam group id, or a case-insensitive name fragment")
        parser.add_argument("--list-days", action="store_true", default=False,
                            help="Print every working day counted, not just the "
                                 "month-by-month totals")
        parser.add_argument("--summary-only", action="store_true", default=False,
                            help="Cross-batch comparison and structural summary "
                                 "only, without the per-exam-group detail")

    def handle(self, *args, **options):
        with schema_context(options["tenant"]):
            self._run(
                options["batch"], options["exam_group"],
                options["list_days"], options["summary_only"],
            )

    # ── Scope ────────────────────────────────────────────────────────────────

    def _batches(self, needle):
        from core.models import Batch

        qs = Batch.objects.filter(is_deleted=False).select_related(
            "course", "academic_year"
        )
        if needle:
            if _looks_like_uuid(needle):
                qs = qs.filter(id=needle)
            else:
                qs = qs.filter(name__icontains=needle)
        return list(qs.order_by("name"))

    def _exam_groups(self, batches, needle):
        from core.models import ExamGroup

        qs = ExamGroup.objects.filter(batch__in=batches).select_related(
            "batch", "batch__academic_year"
        )
        if needle:
            if _looks_like_uuid(needle):
                qs = qs.filter(id=needle)
            else:
                qs = qs.filter(name__icontains=needle)
        return list(qs.order_by("batch__name", "exam_date", "name"))

    # ── Report ───────────────────────────────────────────────────────────────

    def _run(self, batch_needle, group_needle, list_days, summary_only):
        from core.models import AttendanceSettings
        from core.services.calendar_service import SchoolCalendarService

        batches = self._batches(batch_needle)
        if not batches:
            self.stdout.write(self.style.ERROR("No batch matched."))
            return
        groups = self._exam_groups(batches, group_needle)
        if not groups:
            self.stdout.write(self.style.WARNING(
                "No exam group matched — a report card is generated against an "
                "exam group, so without one there is no attendance range to "
                "explain."
            ))
            return

        tenant = batches[0].tenant
        calendar = SchoolCalendarService(tenant)
        self._working_days_report(tenant, calendar, AttendanceSettings)

        # (group, AttendanceRange, total_days, working_day_list)
        rows = [self._measure(calendar, g) for g in groups]

        if not summary_only:
            for row in rows:
                self._group_report(calendar, list_days, *row)

        self._comparison(rows)
        self._stale_cache_report(rows)
        self._structural_summary(calendar, rows)

    def _measure(self, calendar, group):
        from core.services.report_generation_service import ReportGenerationService

        rng = ReportGenerationService.resolve_attendance_range(group)
        if rng.start_date and rng.end_date:
            days = calendar.get_working_day_list(rng.start_date, rng.end_date)
        else:
            days = []
        return group, rng, len(days), days

    # ── Calendar configuration ───────────────────────────────────────────────

    def _working_days_report(self, tenant, calendar, AttendanceSettings):
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Calendar configuration ==="))

        # get_settings() is a get_or_create on a non-unique `tenant` field, so a
        # second row is possible — and then which one shapes every total on
        # every report card is down to insertion order.
        n = AttendanceSettings.objects.filter(tenant=tenant).count()
        if n > 1:
            self.stdout.write(self.style.ERROR(
                f"  {n} AttendanceSettings rows exist for this tenant — only one "
                f"of them is being used, arbitrarily. This must be resolved "
                f"before any total below can be trusted."
            ))

        working = calendar.get_configured_working_days()
        names = ", ".join(_WEEKDAY_NAMES[d] for d in sorted(working)) or "(none)"
        self.stdout.write(f"  working_days: {sorted(working)}  → {names}")
        weekend = sorted(set(working) & {5, 6})
        if weekend:
            self.stdout.write(self.style.WARNING(
                "  includes " + ", ".join(_WEEKDAY_NAMES[d] for d in weekend) +
                " — every one of those in a term is counted as a school day"
            ))
        if not working:
            self.stdout.write(self.style.ERROR(
                "  no working days configured — every total will be 0"
            ))

    # ── Per exam group ───────────────────────────────────────────────────────

    def _group_report(self, calendar, list_days, group, rng, total, days):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== {group.batch.name} / {group.name!r} ==="
        ))
        self.stdout.write(f"  exam_group={group.id} published={group.is_published}")

        # How the range was chosen — the first thing to check, because the
        # 'batch' and 'none' sources mean the term lookup missed.
        self.stdout.write(f"  resolve_exam_group_term() → {rng.term_name!r}")
        if rng.source == "term":
            t = rng.term
            self.stdout.write(
                f"  range from TERM {t.name!r} (order={t.order}, term={t.id}): "
                f"{_day(t.start_date)} .. {_day(t.end_date)}"
            )
        elif rng.source == "batch":
            self.stdout.write(self.style.WARNING(
                f"  range from BATCH dates: {_day(rng.start_date)} .. "
                f"{_day(rng.end_date)}"
            ))
            self.stdout.write(
                f"    No Term row on this exam group matched {rng.term_name!r}. "
                f"Either the exam group has no terms at all (in which case that "
                f"name is the exam group's own), or a term name carries leading "
                f"or trailing whitespace — resolve_exam_group_term strips it and "
                f"the name__iexact lookup then misses. Batch dates usually span "
                f"the whole year, not one term, so the total below will be far "
                f"too high."
            )
        else:
            self.stdout.write(self.style.ERROR(
                "  NO RANGE could be resolved — the report card falls back to "
                "counting raw attendance rows, which is not a working-day count "
                "at all."
            ))
            return

        # Terms that exist but weren't chosen: seeing them side by side is what
        # makes a wrong pick or a wrong date obvious.
        others = [t for t in group.terms.all().order_by("order")]
        if len(others) > 1:
            self.stdout.write("  all terms on this exam group:")
            for t in others:
                mark = " ←chosen" if rng.term and t.id == rng.term.id else ""
                span = calendar.get_working_days(t.start_date, t.end_date)
                self.stdout.write(
                    f"    {t.order}. {t.name!r} {t.start_date} .. {t.end_date} "
                    f"= {span} working days{mark}"
                )

        # Holidays, and what each one is actually worth. A holiday on a Saturday
        # removes nothing, so "we entered the holidays" is not the same as "the
        # total came down".
        holidays = list(calendar.get_holidays(rng.start_date, rng.end_date))
        self.stdout.write(f"  holidays overlapping the range: {len(holidays)}")
        removed = 0
        for ev in holidays:
            # localtime(), not .date(): Event stores datetimes and the DB hands
            # them back in UTC, so a holiday entered at 00:00 Lusaka (UTC+2)
            # reads as the *previous* day under a bare .date(). That is the bug
            # `batch_monthly_attendance_api` has; SchoolCalendarService avoids it
            # by filtering DB-side with __date, and this must agree with it or
            # the listing would contradict the total printed below it.
            start = max(timezone.localtime(ev.start_date).date(), rng.start_date)
            end = min(timezone.localtime(ev.end_date).date(), rng.end_date)
            n = sum(
                1 for d in _dates(start, end)
                if d.weekday() in calendar.get_configured_working_days()
            )
            removed += n
            note = "" if n else "  (falls on non-working days — removes nothing)"
            self.stdout.write(
                f"    {ev.title!r} {start} .. {end} → -{n} working day(s){note}"
            )
        if holidays:
            self.stdout.write(f"    total removed by holidays: {removed}")

        self.stdout.write(self.style.SUCCESS(f"  TOTAL DAYS = {total}"))
        by_month = defaultdict(int)
        for d in days:
            by_month[(d.year, d.month)] += 1
        self.stdout.write("  " + " · ".join(
            f"{_MONTH_NAMES[m]} {n}" for (_y, m), n in sorted(by_month.items())
        ))
        if list_days:
            for d in days:
                self.stdout.write(f"    {_day(d)}")

    # ── Cross-batch comparison ───────────────────────────────────────────────

    def _comparison(self, rows):
        """Term dates live on the exam group, and an exam group belongs to one
        batch — so nothing keeps two grades' terms the same length. If one batch
        is an outlier here, its Term row is the answer and nothing else needs
        investigating."""
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n=== Total days by batch ==="
        ))
        self.stdout.write(
            f"  {'batch':<12} {'term':<22} {'start':<11} {'end':<11} {'days':>5}  source"
        )
        for group, rng, total, _days in sorted(
            rows, key=lambda r: (-r[2], r[0].batch.name)
        ):
            name = (rng.term.name if rng.term else rng.term_name) or "—"
            self.stdout.write(
                f"  {group.batch.name:<12} {name[:22]:<22} "
                f"{str(rng.start_date or '—'):<11} {str(rng.end_date or '—'):<11} "
                f"{total:>5}  {rng.source}"
            )

        # Group by normalised term name so "TERM 1" and "Term 1 " compare.
        by_term = defaultdict(set)
        for group, rng, total, _days in rows:
            name = (rng.term.name if rng.term else rng.term_name) or ""
            by_term[_normalise(name)].add(total)
        # With one exam group in scope there is nothing to compare, and saying
        # "every batch agrees" would be a claim this run cannot support.
        if len(rows) < 2:
            self.stdout.write(
                "\n  Only one exam group is in scope, so there is no comparison "
                "to make. Re-run without --batch/--exam-group to find out "
                "whether other batches carry the same total."
            )
            return

        disagreeing = {k: v for k, v in by_term.items() if len(v) > 1}
        self.stdout.write(
            f"\n  Term names whose total differs between batches: {len(disagreeing)}"
        )
        for key, totals in disagreeing.items():
            self.stdout.write(self.style.WARNING(
                f"    {key or '(unnamed)'}: {sorted(totals)} — same term, "
                f"different lengths, so at least one batch's Term row is wrong"
            ))
        if not disagreeing:
            self.stdout.write(
                "    none — every batch in scope agrees, so a wrong total is "
                "school-wide (missing holidays or working_days), not one "
                "batch's Term row"
            )

    # ── Stale report cache ───────────────────────────────────────────────────

    def _stale_cache_report(self, rows):
        """`total_days` is frozen into StudentReport.report_data at generation
        time. If the calendar was corrected afterwards, the card still shows the
        old number and the only fix is regeneration — no data edit would help."""
        from core.models import StudentReport

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n=== Cached report cards vs a fresh calculation ==="
        ))
        any_reports = False
        for group, _rng, total, _days in rows:
            cached = defaultdict(int)
            for report in StudentReport.objects.filter(exam_group=group).only(
                "report_data"
            ):
                att = (report.report_data or {}).get("attendance") or {}
                if "total_days" in att:
                    cached[att["total_days"]] += 1
            if not cached:
                continue
            any_reports = True
            stale = {k: v for k, v in cached.items() if int(k) != total}
            label = f"{group.batch.name} / {group.name!r}"
            if stale:
                self.stdout.write(self.style.WARNING(
                    f"  {label}: fresh={total} but cards hold "
                    + ", ".join(f"{k} ({v} card(s))" for k, v in sorted(stale.items()))
                    + " — regenerate these"
                ))
            else:
                self.stdout.write(
                    f"  {label}: {sum(cached.values())} card(s), all agree at {total}"
                )
        if not any_reports:
            self.stdout.write(
                "  no generated report cards carry an attendance total — "
                "whatever the school is looking at was rendered live, so the "
                "figures above are what it shows"
            )

    # ── Structural summary ───────────────────────────────────────────────────

    def _structural_summary(self, calendar, rows):
        from core.models import Attendance

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Structural summary ==="))

        # A term boundary on a non-school day means the dates were not copied
        # from the real school calendar — the strongest single signal that a
        # Term row was generated rather than entered.
        self.stdout.write("\nTerm boundaries falling on a non-school day:")
        found = False
        for group, rng, _total, _days in rows:
            if rng.source != "term":
                continue
            for label, d in (("start", rng.start_date), ("end", rng.end_date)):
                if not calendar.is_school_day(d):
                    found = True
                    self.stdout.write(
                        f"  {group.batch.name} / {rng.term.name!r} {label} "
                        f"{_day(d)} is not a school day"
                    )
        if not found:
            self.stdout.write("  none")

        self.stdout.write("\nTerms that overlap or leave gaps:")
        found = False
        seen_groups = set()
        for group, _rng, _total, _days in rows:
            if group.id in seen_groups:
                continue
            seen_groups.add(group.id)
            terms = list(group.terms.all().order_by("start_date"))
            for a, b in zip(terms, terms[1:]):
                if b.start_date <= a.end_date:
                    found = True
                    self.stdout.write(self.style.WARNING(
                        f"  {group.batch.name}: {a.name!r} ends {a.end_date} but "
                        f"{b.name!r} starts {b.start_date} — overlapping, so the "
                        f"same days are counted in both terms"
                    ))
                else:
                    gap = calendar.get_working_days(a.end_date, b.start_date) - 2
                    if gap < 0:
                        gap = 0
                    self.stdout.write(
                        f"  {group.batch.name}: {a.name!r} → {b.name!r} break of "
                        f"{gap} working day(s)"
                    )
        if not found and not seen_groups:
            self.stdout.write("  none")

        # Days everybody was unmarked. Reported as a hint only: no row means
        # "present" in this system, so a school closure the office forgot to
        # enter as an Event and a day when nobody was absent look identical.
        # What makes it worth printing is the contrast — if the batch marks
        # attendance most days, the days it marked none stand out.
        today = timezone.localdate()
        self.stdout.write(
            "\nWorking days already past with no attendance row for anyone in "
            "the batch (candidate unrecorded closures — a hint, not proof: an "
            "unmarked day also means nobody was absent):"
        )
        found = False
        for group, rng, total, days in rows:
            # Days still in the future are unmarked because they haven't
            # happened. Counting them here buries the handful of past days that
            # actually mean something — and a term running past today is common,
            # since the total is a whole-term figure either way.
            elapsed = [d for d in days if d < today]
            if not elapsed:
                continue
            marked = set(
                Attendance.objects.filter(
                    batch=group.batch,
                    month_date__gte=rng.start_date,
                    month_date__lte=rng.end_date,
                ).values_list("month_date", flat=True)
            )
            # Only meaningful for a batch that marks attendance routinely.
            if len(marked) < 0.4 * len(elapsed):
                continue
            blank = [d for d in elapsed if d not in marked]
            if not blank:
                continue
            found = True
            self.stdout.write(
                f"  {group.batch.name} / {rng.term_name!r}: {len(blank)} of "
                f"{len(elapsed)} elapsed working days unmarked "
                f"(batch marks {len(marked)} day(s); {total - len(elapsed)} of "
                f"the term's {total} days are still in the future)"
            )
            for d in blank[:15]:
                self.stdout.write(f"    {_day(d)}")
        if not found:
            self.stdout.write(
                "  none (or no batch marks attendance often enough for this to "
                "mean anything)"
            )

        # Holiday events stored just after local midnight. SchoolCalendarService
        # resolves these DB-side with __date (localtime), but
        # `batch_monthly_attendance_api` expands them in Python with .date() on
        # an aware datetime (UTC) — so in Africa/Lusaka (UTC+2) these are
        # exactly the rows where the register grid and the report card disagree
        # about which day the holiday fell on.
        self.stdout.write(
            "\nHoliday events stored between 00:00 and 02:00 local "
            "(these shift a day in the register grid, though not on the card):"
        )
        found = False
        seen_events = set()
        for _group, rng, _total, days in rows:
            if not days:
                continue
            for ev in calendar.get_holidays(rng.start_date, rng.end_date):
                if ev.id in seen_events:
                    continue
                seen_events.add(ev.id)
                for field in ("start_date", "end_date"):
                    # localtime() honours Django's TIME_ZONE; astimezone() would
                    # use whatever the machine running this happens to be set to.
                    local = timezone.localtime(getattr(ev, field))
                    if local.hour < 2:
                        found = True
                        self.stdout.write(
                            f"  {ev.title!r} {field}={local:%Y-%m-%d %H:%M %Z} "
                            f"event={ev.id}"
                        )
                        break
        if not found:
            self.stdout.write("  none")


def _dates(start, end):
    from datetime import timedelta

    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)
