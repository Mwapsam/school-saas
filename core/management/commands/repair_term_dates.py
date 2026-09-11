"""
Correct the start/end dates of a term across batches.

``Term`` rows hang off ``ExamGroup``, and an exam group belongs to exactly one
batch — so every batch carries its own copy of "when Term 2 runs", with nothing
in the model keeping them in step. A report card's attendance total is a
working-day count over that range (see
``ReportGenerationService.resolve_attendance_range``), so one batch's copy
drifting produces a total that is wrong for that class alone, which reads to the
school as an attendance bug rather than a calendar one.

The dates are given explicitly rather than inferred from what most batches
happen to hold: the school calendar is the authority here, not the majority
vote, and silently rewriting term rows to match a guess is not something that
should be possible by accident.

Report cards cache their totals in ``StudentReport.report_data``, so fixing a
term does not fix the cards already generated from it. Those are listed at the
end and have to be regenerated.

Dry run by default, like repair_orphaned_exam_subjects.

Usage:
    # See what would change
    python manage.py repair_term_dates --tenant=<schema> \
        --term="Term 2 2026" --start=2026-05-11 --end=2026-08-07

    # Apply, to one batch only
    python manage.py repair_term_dates --tenant=<schema> \
        --term="Term 2 2026" --start=2026-05-11 --end=2026-08-07 \
        --batch=1B --execute
"""

import re
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_tenants.utils import schema_context

# Same normalisation the other calendar commands use, so 'TERM 2 2026' and
# 'Term 2 2026' are one term rather than two.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalise(name: str) -> str:
    return _NON_ALNUM.sub("", (name or "").lower())


def _looks_like_uuid(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F-]{32,36}", value or ""))


def _parse_date(value: str, flag: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise CommandError(f"{flag} must be an ISO date, e.g. 2026-05-11 (got {value!r})")


class Command(BaseCommand):
    help = "Set a term's start and end dates across batches, with a dry run first."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--term", required=True,
                            help="Term name; matched ignoring case and punctuation")
        parser.add_argument("--start", required=True, help="New start date (YYYY-MM-DD)")
        parser.add_argument("--end", required=True, help="New end date (YYYY-MM-DD)")
        parser.add_argument("--batch", default=None,
                            help="Batch id or name fragment; omitted means every "
                                 "batch holding a term of this name")
        parser.add_argument("--execute", action="store_true", default=False)

    def handle(self, *args, **options):
        start = _parse_date(options["start"], "--start")
        end = _parse_date(options["end"], "--end")
        if start > end:
            raise CommandError(f"--start {start} is after --end {end}")

        if not options["execute"]:
            self.stdout.write(self.style.WARNING("DRY RUN — pass --execute to apply\n"))
        with schema_context(options["tenant"]):
            self._repair(options["term"], start, end, options["batch"], options["execute"])

    def _repair(self, term_needle, start, end, batch_needle, execute):
        from core.models import StudentReport, Term
        from core.services.calendar_service import SchoolCalendarService

        qs = Term.objects.select_related(
            "exam_group", "exam_group__batch"
        ).order_by("exam_group__batch__name")
        if batch_needle:
            if _looks_like_uuid(batch_needle):
                qs = qs.filter(exam_group__batch_id=batch_needle)
            else:
                qs = qs.filter(exam_group__batch__name__icontains=batch_needle)

        wanted = _normalise(term_needle)
        terms = [t for t in qs if _normalise(t.name) == wanted]
        if not terms:
            self.stdout.write(self.style.ERROR(
                f"No term matched {term_needle!r}"
                + (f" in batches matching {batch_needle!r}" if batch_needle else "")
            ))
            return

        calendar = SchoolCalendarService(terms[0].tenant)
        target_total = calendar.get_working_days(start, end)
        self.stdout.write(
            f"Target: {start} .. {end} = {target_total} working days\n"
        )

        changing, already = [], []
        for term in terms:
            if (term.start_date, term.end_date) == (start, end):
                already.append(term)
                continue
            changing.append(term)
            before = calendar.get_working_days(term.start_date, term.end_date)
            self.stdout.write(
                f"  {term.exam_group.batch.name:<16} {term.name!r} "
                f"{term.start_date} .. {term.end_date} ({before} days) "
                f"→ {start} .. {end} ({target_total} days)  term={term.id}"
            )

        self.stdout.write(
            f"\n{len(changing)} term row(s) to change, "
            f"{len(already)} already correct."
        )

        if not changing:
            return

        if execute:
            with transaction.atomic():
                for term in changing:
                    term.start_date = start
                    term.end_date = end
                    term.save(update_fields=["start_date", "end_date", "updated_at"])
            self.stdout.write(self.style.SUCCESS(f"\nUpdated {len(changing)} term row(s)."))

        # Cached cards do not follow the term. Naming them is the difference
        # between "fixed" and "fixed for reports generated from now on".
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n=== Report cards that need regenerating ==="
        ))
        found = False
        for term in changing:
            stale = 0
            for report in StudentReport.objects.filter(
                exam_group=term.exam_group
            ).only("report_data"):
                att = (report.report_data or {}).get("attendance") or {}
                if "total_days" in att and int(att["total_days"]) != target_total:
                    stale += 1
            if stale:
                found = True
                self.stdout.write(
                    f"  {term.exam_group.batch.name} / {term.exam_group.name!r}: "
                    f"{stale} card(s) still cache the old total "
                    f"(exam_group={term.exam_group.id})"
                )
        if not found:
            self.stdout.write("  none")
        else:
            self.stdout.write(
                "\n  Regenerate these from Reports → the batch's report template, "
                "or verify afterwards with:\n"
                "    python manage.py diagnose_attendance_totals --tenant=<schema>"
            )
