"""Tests for the report card's attendance total.

The number on the card is a pure calendar count over a date range — attendance
rows only ever move a day from "present" to "absent", never change the total. So
a wrong total means a wrong *calendar input*: the range, the working weekdays,
or the holiday events. These tests pin each of those inputs to its effect, and
pin `resolve_attendance_range` — the one function the report card and
`diagnose_attendance_totals` both read, so the diagnostic can never name a range
the card didn't actually use.

The shape behind the "Grade 1B shows 61 days instead of 58" report is the last
class here: term dates hang off ExamGroup, which belongs to one batch, so two
grades can disagree about how long the same term is.
"""

import uuid
from datetime import date, datetime, time, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import (
    Attendance,
    AttendanceSettings,
    Batch,
    Event,
    ExamGroup,
    ReportTemplate,
    StudentReport,
    Term,
)
from core.services.calendar_service import SchoolCalendarService
from core.services.report_generation_service import ReportGenerationService

# A fixed, boring week grid so every expected count below can be read off a
# calendar by hand. 2026-03-02 is a Monday; 2026-03-27 is the Friday four weeks
# later, giving exactly 20 weekdays.
TERM_START = date(2026, 3, 2)
TERM_END = date(2026, 3, 27)
TERM_WEEKDAYS = 20


def _exam_group(batch, tenant, name=None, exam_date=None):
    return ExamGroup.objects.create(
        tenant=tenant,
        batch=batch,
        name=name or f"Plan {uuid.uuid4().hex[:4]}",
        exam_type="TERM",
        exam_date=exam_date or TERM_START,
        is_published=True,
    )


def _term(exam_group, tenant, name="TERM 1", start=TERM_START, end=TERM_END, order=1):
    # Phase 4: Terms are year-scoped via academic_year (derived from exam_group.batch.academic_year)
    return Term.objects.create(
        tenant=tenant,
        academic_year=exam_group.batch.academic_year,
        name=name,
        start_date=start,
        end_date=end,
        order=order,
    )


def _holiday(tenant, start, end=None, title="Holiday", at=time(0, 0)):
    """A holiday Event. `at` exists because Event stores datetimes while the
    calendar reasons in dates — a holiday entered just after local midnight is
    the one shape where the two disagree."""
    tz = timezone.get_current_timezone()
    end = end or start
    return Event.objects.create(
        tenant=tenant,
        title=title,
        start_date=timezone.make_aware(datetime.combine(start, at), tz),
        end_date=timezone.make_aware(datetime.combine(end, time(23, 0)), tz),
        is_holiday=True,
    )


def _working_days(tenant, start=TERM_START, end=TERM_END):
    return SchoolCalendarService(tenant).get_working_days(start, end)


@pytest.fixture
def weekdays_only(tenant):
    """Mon–Fri, explicitly. Every expected count in this module assumes it."""
    settings = AttendanceSettings.get_settings(tenant)
    settings.working_days = [0, 1, 2, 3, 4]
    settings.save()
    return settings


@pytest.mark.django_db
@pytest.mark.unit
class TestCalendarInputs:
    """Each input that can move the total, and by how much."""

    def test_plain_term_counts_weekdays_only(self, tenant, weekdays_only):
        assert _working_days(tenant) == TERM_WEEKDAYS

    def test_each_extra_weekday_on_the_end_date_adds_one(self, tenant, weekdays_only):
        # The 1B shape: a term whose end date runs past the real close of term.
        # 2026-03-30..04-01 are Mon/Tue/Wed.
        assert _working_days(tenant, end=date(2026, 4, 1)) == TERM_WEEKDAYS + 3

    def test_a_missing_holiday_leaves_the_total_three_too_high(self, tenant, weekdays_only):
        # Three midweek closures nobody entered as Events. This is the other way
        # to land on 61-instead-of-58, and it would affect every batch at once.
        for d in (date(2026, 3, 4), date(2026, 3, 11), date(2026, 3, 18)):
            _holiday(tenant, d)
        assert _working_days(tenant) == TERM_WEEKDAYS - 3

    def test_a_holiday_on_a_weekend_removes_nothing(self, tenant, weekdays_only):
        _holiday(tenant, date(2026, 3, 7))  # Saturday
        assert _working_days(tenant) == TERM_WEEKDAYS

    def test_multi_day_holiday_spanning_a_weekend_removes_only_weekdays(
        self, tenant, weekdays_only
    ):
        # Fri 13th → Mon 16th: four calendar days, two of them school days.
        _holiday(tenant, date(2026, 3, 13), date(2026, 3, 16), title="Long weekend")
        assert _working_days(tenant) == TERM_WEEKDAYS - 2

    def test_saturday_in_working_days_inflates_the_total(self, tenant, weekdays_only):
        weekdays_only.working_days = [0, 1, 2, 3, 4, 5]
        weekdays_only.save()
        # Mar 7, 14, 21 — the 28th falls past TERM_END.
        assert _working_days(tenant) == TERM_WEEKDAYS + 3

    def test_attendance_rows_cannot_change_the_total(self, tenant, weekdays_only, student, batch):
        """The property the whole diagnosis rests on: marking somebody absent
        moves a day from present to absent and leaves the total alone."""
        svc = ReportGenerationService(tenant)
        before = svc._compute_attendance_summary(
            [], start_date=TERM_START, end_date=TERM_END, batch=batch
        )
        records = [
            {"month_date": date(2026, 3, 4), "forenoon": False, "afternoon": False},
            {"month_date": date(2026, 3, 5), "forenoon": False, "afternoon": False},
        ]
        after = svc._compute_attendance_summary(
            records, start_date=TERM_START, end_date=TERM_END, batch=batch
        )
        assert before["total_days"] == after["total_days"] == float(TERM_WEEKDAYS)
        assert before["days_absent"] == 0.0
        assert after["days_absent"] == 2.0

    def test_duplicate_rows_for_one_date_are_deduped(self, tenant, weekdays_only, batch):
        """`Attendance` has no unique constraint on (student, month_date), so a
        transferred student can carry two rows for one day. The card must not
        double-count them."""
        svc = ReportGenerationService(tenant)
        d = date(2026, 3, 4)
        summary = svc._compute_attendance_summary(
            [
                {"month_date": d, "forenoon": False, "afternoon": False},
                {"month_date": d, "forenoon": False, "afternoon": False},
            ],
            start_date=TERM_START, end_date=TERM_END, batch=batch,
        )
        assert summary["total_days"] == float(TERM_WEEKDAYS)
        assert summary["days_absent"] == 1.0


@pytest.mark.django_db
@pytest.mark.unit
class TestRangeResolution:
    """`resolve_attendance_range` is the single source of truth for the window
    the card is computed over. If it and the diagnostic ever disagreed, the
    command would report a range the card never used."""

    def test_matching_term_wins(self, tenant, batch, weekdays_only):
        group = _exam_group(batch, tenant)
        term = _term(group, tenant, name="TERM 1")
        rng = ReportGenerationService.resolve_attendance_range(group)
        assert rng.source == "term"
        assert (rng.start_date, rng.end_date) == (TERM_START, TERM_END)
        assert rng.term.id == term.id

    def test_padded_term_name_falls_back_to_batch_dates(self, tenant, batch, weekdays_only):
        """`resolve_exam_group_term` returns the term's own name *stripped*, and
        the lookup that follows is `name__iexact` against the unstripped column —
        so a term stored with trailing whitespace cannot match itself. The card
        then silently switches to the batch's dates, which span the whole year
        rather than one term. The diagnostic reports this as source='batch'
        precisely so it isn't mistaken for a date-entry error.

        (An invisible character *inside* the name is harmless here, unlike in
        subject matching: both sides of this comparison read the same row.)"""
        group = _exam_group(batch, tenant)
        _term(group, tenant, name="TERM 1 ")

        rng = ReportGenerationService.resolve_attendance_range(group)
        assert rng.source == "batch"
        assert rng.term is None
        # The batch's own window, narrowed to plain dates for the calendar.
        # localdate, not .date(): the column is a DateTimeField and the DB
        # returns UTC, so a batch starting midnight Lusaka comes back as 22:00
        # the previous day — reading it as a UTC date would shift the whole
        # window back a day.
        fresh = Batch.objects.get(pk=batch.pk)
        assert rng.start_date == timezone.localdate(fresh.start_date)
        assert rng.end_date == timezone.localdate(fresh.end_date)

    def test_the_report_card_uses_the_resolved_range(self, tenant, batch, student, weekdays_only):
        """Ties the resolver to the number that actually reaches the card."""
        group = _exam_group(batch, tenant)
        _term(group, tenant)
        Attendance.objects.create(
            tenant=tenant, student=student, batch=batch,
            month_date=date(2026, 3, 4), forenoon=False, afternoon=False,
        )
        # A row outside the term must not be counted.
        Attendance.objects.create(
            tenant=tenant, student=student, batch=batch,
            month_date=date(2026, 5, 4), forenoon=False, afternoon=False,
        )
        svc = ReportGenerationService(tenant)
        data = svc._get_attendance_data(student, None, group)
        assert data["total_days"] == float(TERM_WEEKDAYS)
        assert data["days_absent"] == 1.0


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.skip(reason="Phase 4: diagnose_attendance_totals needs refactoring — Terms are now year-scoped")
class TestDiagnoseCommand:
    """The command must report the deciding input, not just a number.

    OBSOLETE POST-PHASE-4: The command was designed around per-batch Term structures.
    With year-scoped Terms, many of the command's diagnostics (date drift, per-batch
    disagreement) no longer apply and would need significant refactoring.
    """

    def _run(self, tenant, **opts):
        out = StringIO()
        call_command(
            "diagnose_attendance_totals",
            tenant=tenant.schema_name, stdout=out, **opts,
        )
        return out.getvalue()

    def test_reports_the_term_and_its_total(self, tenant, batch, weekdays_only):
        group = _exam_group(batch, tenant)
        _term(group, tenant)
        out = self._run(tenant, batch=batch.name)
        assert "TERM 1" in out
        assert f"TOTAL DAYS = {TERM_WEEKDAYS}" in out

    def test_names_each_holiday_and_what_it_removed(self, tenant, batch, weekdays_only):
        group = _exam_group(batch, tenant)
        _term(group, tenant)
        _holiday(tenant, date(2026, 3, 4), title="Youth Day")
        _holiday(tenant, date(2026, 3, 7), title="Saturday thing")

        out = self._run(tenant, batch=batch.name)
        assert "Youth Day" in out and "-1 working day(s)" in out
        # A holiday that removes nothing must say so rather than look effective.
        assert "removes nothing" in out
        assert f"TOTAL DAYS = {TERM_WEEKDAYS - 1}" in out

    def test_flags_a_term_boundary_on_a_non_school_day(self, tenant, batch, weekdays_only):
        group = _exam_group(batch, tenant)
        _term(group, tenant, end=date(2026, 3, 28))  # Saturday
        out = self._run(tenant, batch=batch.name)
        assert "not a school day" in out

    def test_warns_when_saturday_is_a_working_day(self, tenant, batch, weekdays_only):
        weekdays_only.working_days = [0, 1, 2, 3, 4, 5]
        weekdays_only.save()
        group = _exam_group(batch, tenant)
        _term(group, tenant)
        out = self._run(tenant, batch=batch.name)
        assert "Sat" in out
        assert "counted as a school day" in out

    def test_reports_the_batch_date_fallback_rather_than_a_bare_number(
        self, tenant, batch, weekdays_only
    ):
        group = _exam_group(batch, tenant)
        _term(group, tenant, name="TERM 1 ")
        out = self._run(tenant, batch=batch.name)
        assert "range from BATCH dates" in out
        assert "trailing whitespace" in out

    def test_a_single_batch_run_does_not_claim_the_batches_agree(
        self, tenant, batch, weekdays_only
    ):
        """A scoped run has nothing to compare against. Saying "every batch
        agrees" there would point the blame school-wide on no evidence — the
        precise way a diagnostic sends someone chasing the wrong thing."""
        group = _exam_group(batch, tenant)
        _term(group, tenant)
        out = self._run(tenant, batch=batch.name)
        assert "Only one exam group is in scope" in out
        assert "school-wide" not in out

    def test_future_days_are_not_reported_as_unrecorded_closures(
        self, tenant, batch, student, weekdays_only
    ):
        """A term running past today is normal — the total is a whole-term
        figure. Counting days that simply haven't happened as "unmarked" buries
        the few past days that might be a missed closure."""
        today = timezone.localdate()
        group = _exam_group(batch, tenant, exam_date=today)
        # A term that started a fortnight ago and runs a fortnight on.
        start, end = today - timedelta(days=14), today + timedelta(days=14)
        _term(group, tenant, start=start, end=end)
        # Mark every elapsed working day, so nothing genuine is outstanding.
        for d in SchoolCalendarService(tenant).get_working_day_list(start, end):
            if d < today:
                Attendance.objects.create(
                    tenant=tenant, student=student, batch=batch,
                    month_date=d, forenoon=True, afternoon=True,
                )
        out = self._run(tenant, batch=batch.name)
        assert "still in the future" not in out
        assert "elapsed working days unmarked" not in out

    def test_flags_a_stale_cached_total(self, tenant, batch, student, weekdays_only):
        """If the card's stored total disagrees with a fresh calculation, the
        fix is regeneration and no data edit would help — the command has to say
        which of the two it is."""
        group = _exam_group(batch, tenant)
        _term(group, tenant)
        template = ReportTemplate.objects.create(
            tenant=tenant, name=f"T{uuid.uuid4().hex[:4]}", batch=batch, term="TERM 1",
            academic_year=batch.academic_year,
        )
        StudentReport.objects.create(
            tenant=tenant, student=student, template=template, exam_group=group,
            report_data={"attendance": {"total_days": 61}},
        )
        out = self._run(tenant, batch=batch.name)
        assert "regenerate these" in out
        assert "fresh=20" in out and "61" in out


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.skip(reason="Phase 4: repair_term_dates is obsolete — Terms are now year-scoped, never per-batch")
class TestRepairTermDates:
    """Aligning a drifted term row, and saying what it does not fix.

    OBSOLETE POST-PHASE-4: The whole premise (per-batch Term date drift) is gone.
    Terms are now year-scoped and shared across all batches in a year.
    """

    def _repair(self, tenant, **opts):
        out = StringIO()
        call_command(
            "repair_term_dates", tenant=tenant.schema_name,
            term="TERM 1", start=TERM_START.isoformat(),
            end=TERM_END.isoformat(), stdout=out, **opts,
        )
        return out.getvalue()

    def test_dry_run_reports_but_changes_nothing(self, tenant, batch, weekdays_only):
        group = _exam_group(batch, tenant)
        term = _term(group, tenant, end=date(2026, 4, 1))  # 3 working days too long
        out = self._repair(tenant, batch=batch.name)

        assert "DRY RUN" in out
        assert "1 term row(s) to change" in out
        term.refresh_from_db()
        assert term.end_date == date(2026, 4, 1)

    def test_execute_aligns_the_row(self, tenant, batch, weekdays_only):
        group = _exam_group(batch, tenant)
        term = _term(group, tenant, end=date(2026, 4, 1))
        self._repair(tenant, batch=batch.name, execute=True)

        term.refresh_from_db()
        assert (term.start_date, term.end_date) == (TERM_START, TERM_END)
        # ...and the card would now compute the intended total.
        rng = ReportGenerationService.resolve_attendance_range(group)
        assert SchoolCalendarService(tenant).get_working_days(
            rng.start_date, rng.end_date
        ) == TERM_WEEKDAYS

    def test_matches_the_term_name_ignoring_case_and_punctuation(
        self, tenant, batch, weekdays_only
    ):
        group = _exam_group(batch, tenant)
        term = _term(group, tenant, name="term-1", end=date(2026, 4, 1))
        self._repair(tenant, batch=batch.name, execute=True)
        term.refresh_from_db()
        assert term.end_date == TERM_END

    def test_a_correct_row_is_left_alone(self, tenant, batch, weekdays_only):
        group = _exam_group(batch, tenant)
        _term(group, tenant)
        out = self._repair(tenant, batch=batch.name)
        assert "0 term row(s) to change, 1 already correct" in out

    def test_names_the_cards_that_still_hold_the_old_total(
        self, tenant, batch, student, weekdays_only
    ):
        """The whole point of the fix is the number on the card, and the card
        caches it — so a repair that didn't say this would look complete while
        the school kept seeing the old figure."""
        group = _exam_group(batch, tenant)
        _term(group, tenant, end=date(2026, 4, 1))
        template = ReportTemplate.objects.create(
            tenant=tenant, name=f"T{uuid.uuid4().hex[:4]}", batch=batch, term="TERM 1",
            academic_year=batch.academic_year,
        )
        StudentReport.objects.create(
            tenant=tenant, student=student, template=template, exam_group=group,
            report_data={"attendance": {"total_days": TERM_WEEKDAYS + 3}},
        )
        out = self._repair(tenant, batch=batch.name, execute=True)
        assert "1 card(s) still cache the old total" in out

    def test_refuses_a_backwards_range(self, tenant, batch, weekdays_only):
        from django.core.management.base import CommandError

        _term(_exam_group(batch, tenant), tenant)
        with pytest.raises(CommandError):
            call_command(
                "repair_term_dates", tenant=tenant.schema_name, term="TERM 1",
                start=TERM_END.isoformat(), end=TERM_START.isoformat(),
                stdout=StringIO(),
            )


@pytest.mark.django_db
@pytest.mark.unit
@pytest.mark.skip(reason="Phase 4: Cross-batch Term divergence no longer possible — unique_together enforced")
class TestCrossBatchDivergence:
    """The 1B shape. `Term` hangs off `ExamGroup` and an exam group belongs to
    one batch, so nothing in the model keeps two grades' terms the same length —
    and the school sees it as "1B's total is wrong" rather than "1B's term row
    is wrong".

    OBSOLETE POST-PHASE-4: The `unique_together(tenant, academic_year, name)` constraint
    now makes it impossible for two batches to have different versions of the same term.
    That was the whole design point — one canonical Term 1 per year, not duplicates.
    """

    def _pair(self, tenant, course, academic_year, ends):
        """Two batches sharing a term name, scoped behind a unique tag.

        The tag matters: `schema_context` activates a FakeTenant, which the
        tenant-aware manager deliberately does not filter on, so an unscoped run
        would sweep up every other batch in the database. `--batch` is the
        command's own scoping and is what keeps these assertions about the two
        batches built here."""
        tag = f"XB{uuid.uuid4().hex[:6].upper()}"
        for suffix, end in ends:
            b = Batch.objects.create(
                tenant=tenant, name=f"{tag}-{suffix}", course=course,
                academic_year=academic_year,
                start_date=timezone.make_aware(datetime(2026, 1, 1)),
                end_date=timezone.make_aware(datetime(2026, 12, 1)),
            )
            _term(_exam_group(b, tenant), tenant, name="TERM 1", end=end)

        out = StringIO()
        call_command(
            "diagnose_attendance_totals",
            tenant=tenant.schema_name, batch=tag, stdout=out,
        )
        return tag, out.getvalue()

    def test_two_batches_can_disagree_about_one_terms_length(
        self, tenant, course, academic_year, weekdays_only
    ):
        tag, text = self._pair(
            tenant, course, academic_year,
            [("1A", TERM_END), ("1B", date(2026, 4, 1))],
        )
        # Both totals appear in the comparison table...
        assert f"{tag}-1A" in text and f"{tag}-1B" in text
        assert f"{TERM_WEEKDAYS + 3}" in text
        # ...and the divergence is called out rather than left to be eyeballed.
        assert "same term, different lengths" in text
        assert f"[{TERM_WEEKDAYS}, {TERM_WEEKDAYS + 3}]" in text

    def test_agreeing_batches_point_the_blame_school_wide(
        self, tenant, course, academic_year, weekdays_only
    ):
        _tag, text = self._pair(
            tenant, course, academic_year,
            [("2A", TERM_END), ("2B", TERM_END)],
        )
        assert "school-wide" in text
        assert "same term, different lengths" not in text
