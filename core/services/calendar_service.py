from datetime import datetime, date, timedelta
from typing import List, Any
from django.db.models import Q, QuerySet

from core.models import Event, AttendanceSettings, Term


class SchoolCalendarService:
    """
    Central service for school calendar and working-day calculations.

    Provides a single source of truth for whether a date is a school day,
    accounting for configured working days (weekdays), holidays, and events.
    All attendance and report-card logic should query through this service
    rather than duplicating weekend/holiday checks inline.

    This is a utility service (not a CRUD service) that works with multiple
    models (Event, AttendanceSettings), so it doesn't inherit from TenantAwareService.
    """

    def __init__(self, tenant):
        self.tenant = tenant
        self._holidays_cache = {}
        self._settings_cache = None

    def _get_settings(self) -> AttendanceSettings:
        """Get tenant's attendance settings (cached per instance)."""
        if self._settings_cache is None:
            self._settings_cache = AttendanceSettings.get_settings(self.tenant)
        return self._settings_cache

    def _get_holidays_for_range(self, start_date: date, end_date: date) -> set:
        """
        Fetch and cache holiday dates for a range. Returns a set of date objects
        for all holidays (Event.is_holiday=True) in the range, expanding each
        matching event across every date it covers (not just its start date) so
        multi-day breaks are fully recognized.
        """
        cache_key = (start_date, end_date)
        if cache_key not in self._holidays_cache:
            events = Event.objects.filter(
                tenant=self.tenant,
                is_holiday=True,
                start_date__date__lte=end_date,
                end_date__date__gte=start_date,
            ).values_list('start_date__date', 'end_date__date')

            holidays = set()
            for ev_start, ev_end in events:
                day = max(ev_start, start_date)
                last = min(ev_end, end_date)
                while day <= last:
                    holidays.add(day)
                    day += timedelta(days=1)

            self._holidays_cache[cache_key] = holidays
        return self._holidays_cache[cache_key]

    def is_school_day(self, target_date: date) -> bool:
        """
        Check if a given date is a school day.

        A date is a school day if:
        1. Its weekday (0=Monday, 6=Sunday) is in the configured working_days list
        2. There is no holiday (Event.is_holiday=True) covering that date

        Args:
            target_date: Date to check

        Returns:
            True if the date is a school day, False otherwise
        """
        settings = self._get_settings()

        # Check if weekday is a working day
        if target_date.weekday() not in settings.working_days:
            return False

        # Check if it's a holiday
        holidays = self._get_holidays_for_range(target_date, target_date)
        return target_date not in holidays

    def is_locked(self, target_date: date, *, allow_admin: bool = False) -> bool:
        """
        Check whether attendance for a date is locked from further changes.

        Locked when the tenant's AttendanceSettings has mark_frequency='lock'
        and the date is older than lock_after_days. allow_admin_unlock lets an
        admin caller (allow_admin=True) bypass the lock; a non-admin caller
        (e.g. a teacher) is never allowed to bypass it, regardless of that
        setting.

        Args:
            target_date: Date to check
            allow_admin: Whether the caller is an admin eligible for the
                tenant's allow_admin_unlock exception

        Returns:
            True if attendance for this date can no longer be marked/edited
        """
        settings = self._get_settings()

        if settings.mark_frequency != 'lock':
            return False

        days_elapsed = (date.today() - target_date).days
        if days_elapsed <= settings.lock_after_days:
            return False

        return not (allow_admin and settings.allow_admin_unlock)

    def get_working_day_list(self, start_date: date, end_date: date) -> List[date]:
        """
        Get a list of all working days between start_date and end_date (inclusive).

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of date objects that are school days
        """
        working_days = []
        current = start_date
        holidays = self._get_holidays_for_range(start_date, end_date)
        settings = self._get_settings()

        while current <= end_date:
            if current.weekday() in settings.working_days and current not in holidays:
                working_days.append(current)
            current += timedelta(days=1)

        return working_days

    def get_working_days(self, start_date: date, end_date: date) -> int:
        """
        Count the number of working days between start_date and end_date (inclusive).

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Count of school days in the range
        """
        return len(self.get_working_day_list(start_date, end_date))

    def get_holidays(self, start_date: date, end_date: date) -> QuerySet:
        """
        Get all holidays (Event.is_holiday=True) that overlap a date range,
        including events that started before the range but extend into it.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            QuerySet of Event objects marked as holidays
        """
        return Event.objects.filter(
            tenant=self.tenant,
            is_holiday=True,
            start_date__date__lte=end_date,
            end_date__date__gte=start_date,
        ).order_by('start_date')

    def get_events(self, start_date: date, end_date: date) -> QuerySet:
        """
        Get all events (any kind) that overlap a date range, including events
        that started before the range but extend into it.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            QuerySet of Event objects
        """
        return Event.objects.filter(
            tenant=self.tenant,
            start_date__date__lte=end_date,
            end_date__date__gte=start_date,
        ).order_by('start_date')

    def get_configured_working_days(self) -> List[int]:
        """
        Tenant's configured working weekdays (0=Monday..6=Sunday).

        Returns:
            List of weekday integers the school operates on
        """
        return self._get_settings().working_days

    def get_upcoming_holidays(self, limit: int = 10) -> QuerySet:
        """
        Get the next N holidays from today.

        Args:
            limit: Number of holidays to fetch

        Returns:
            QuerySet of upcoming Event objects marked as holidays
        """
        today = date.today()
        return Event.objects.filter(
            tenant=self.tenant,
            is_holiday=True,
            start_date__date__gte=today,
        ).order_by('start_date')[:limit]

    def is_within_active_term(self, academic_year, target_date: date) -> bool:
        """
        Check if a date falls inside any Term for the given academic year.

        Used to pause attendance marking in the gap after one term ends and
        before the next begins. This is a strict containment check — a date
        in the gap between terms will return False.

        Args:
            academic_year: The academic year to search within
            target_date: Date to check

        Returns:
            True if target_date is covered by a Term in the academic year
        """
        if academic_year is None:
            return False
        return Term.objects.filter(
            tenant=self.tenant,
            academic_year=academic_year,
            start_date__lte=target_date,
            end_date__gte=target_date,
        ).exists()
