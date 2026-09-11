from django.test import TestCase
from datetime import date, timedelta
from core.models import School, AttendanceSettings, Event, AcademicYear
from core.services.calendar_service import SchoolCalendarService


class SchoolCalendarServiceTestCase(TestCase):
    """Unit tests for SchoolCalendarService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = School.objects.create(
            name="Test School",
            code="CALSVC01",
            schema_name="test_calsvc001"
        )
        self.settings = AttendanceSettings.get_settings(self.tenant)
        self.calendar = SchoolCalendarService(self.tenant)

        self.academic_year = AcademicYear.objects.create(
            tenant=self.tenant,
            name="2024-2025",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            is_active=True
        )

    def test_default_working_days(self):
        """Test that default working days are Monday-Friday"""
        self.assertEqual(self.settings.working_days, [0, 1, 2, 3, 4])

    def test_is_school_day_weekday(self):
        """Test that a weekday is recognized as a school day"""
        # Monday, 2024-01-08
        monday = date(2024, 1, 8)
        self.assertTrue(self.calendar.is_school_day(monday))

    def test_is_school_day_weekend(self):
        """Test that Saturday and Sunday are not school days by default"""
        # Saturday, 2024-01-06
        saturday = date(2024, 1, 6)
        self.assertFalse(self.calendar.is_school_day(saturday))

        # Sunday, 2024-01-07
        sunday = date(2024, 1, 7)
        self.assertFalse(self.calendar.is_school_day(sunday))

    def test_is_school_day_with_holiday(self):
        """Test that a holiday is not a school day"""
        # Monday, 2024-01-15 (normally a school day)
        holiday_date = date(2024, 1, 15)
        event = Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="Public Holiday",
            start_date=f"{holiday_date} 00:00:00",
            end_date=f"{holiday_date} 23:59:59",
            is_holiday=True
        )

        # The event already exists in the DB, so even a fresh (empty) cache
        # should pick it up on the very first query.
        self.assertFalse(self.calendar.is_school_day(holiday_date))

        # Still holds after a cache reset forces a fresh DB query.
        self.calendar._holidays_cache = {}
        self.assertFalse(self.calendar.is_school_day(holiday_date))

    def test_get_working_days_count(self):
        """Test counting working days in a range"""
        # Week of 2024-01-08 to 2024-01-12 (Mon-Fri, no holidays)
        start = date(2024, 1, 8)
        end = date(2024, 1, 12)
        count = self.calendar.get_working_days(start, end)
        self.assertEqual(count, 5)

    def test_get_working_days_with_weekend(self):
        """Test that weekends are excluded from working day count"""
        # 2024-01-08 to 2024-01-14 (Mon-Sun, includes Sat-Sun)
        start = date(2024, 1, 8)
        end = date(2024, 1, 14)
        count = self.calendar.get_working_days(start, end)
        self.assertEqual(count, 5)  # Mon-Fri only

    def test_get_working_day_list(self):
        """Test getting list of working days"""
        start = date(2024, 1, 8)
        end = date(2024, 1, 12)
        working_days = self.calendar.get_working_day_list(start, end)

        expected = [
            date(2024, 1, 8),   # Monday
            date(2024, 1, 9),   # Tuesday
            date(2024, 1, 10),  # Wednesday
            date(2024, 1, 11),  # Thursday
            date(2024, 1, 12),  # Friday
        ]
        self.assertEqual(working_days, expected)

    def test_custom_working_days(self):
        """Test with custom working days (including Saturday)"""
        self.settings.working_days = [0, 1, 2, 3, 4, 5]  # Mon-Sat
        self.settings.save()
        self.calendar._settings_cache = None

        # Saturday should now be a school day
        saturday = date(2024, 1, 6)
        self.assertTrue(self.calendar.is_school_day(saturday))

        # Sunday should still not be a school day
        sunday = date(2024, 1, 7)
        self.assertFalse(self.calendar.is_school_day(sunday))

    def test_get_holidays(self):
        """Test fetching holidays in a date range"""
        holiday1 = Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="New Year",
            start_date="2024-01-01 00:00:00",
            end_date="2024-01-01 23:59:59",
            is_holiday=True
        )
        holiday2 = Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="Republic Day",
            start_date="2024-01-26 00:00:00",
            end_date="2024-01-26 23:59:59",
            is_holiday=True
        )

        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        holidays = self.calendar.get_holidays(start, end)

        self.assertEqual(holidays.count(), 2)
        holiday_ids = set(holidays.values_list('id', flat=True))
        self.assertIn(holiday1.id, holiday_ids)
        self.assertIn(holiday2.id, holiday_ids)

    def test_working_days_with_multiple_holidays(self):
        """Test working day count with multiple holidays"""
        # Create holidays for 2024-01-11, 2024-01-12
        Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="Holiday 1",
            start_date="2024-01-11 00:00:00",
            end_date="2024-01-11 23:59:59",
            is_holiday=True
        )
        Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="Holiday 2",
            start_date="2024-01-12 00:00:00",
            end_date="2024-01-12 23:59:59",
            is_holiday=True
        )

        # Count for 2024-01-08 to 2024-01-12
        # Normally 5 days, but 2 are holidays = 3 working days
        start = date(2024, 1, 8)
        end = date(2024, 1, 12)
        self.calendar._holidays_cache = {}
        count = self.calendar.get_working_days(start, end)
        self.assertEqual(count, 3)

    def test_is_school_day_multi_day_holiday_range(self):
        """A multi-day holiday event (e.g. a mid-term break) should be
        recognized on every day it covers, not just its first day."""
        # Mon 2024-03-11 to Fri 2024-03-15
        Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="Mid-term Break",
            start_date="2024-03-11 00:00:00",
            end_date="2024-03-15 23:59:59",
            is_holiday=True
        )

        for day in range(11, 16):
            self.assertFalse(
                self.calendar.is_school_day(date(2024, 3, day)),
                msg=f"2024-03-{day} should be a holiday"
            )

        # The Friday before and the Monday after should still be school days
        self.assertTrue(self.calendar.is_school_day(date(2024, 3, 8)))
        self.assertTrue(self.calendar.is_school_day(date(2024, 3, 18)))

    def test_get_working_day_list_excludes_multi_day_holiday_range(self):
        """get_working_day_list/get_working_days should exclude every day
        of a multi-day holiday event, not just its start date."""
        Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="Mid-term Break",
            start_date="2024-03-11 00:00:00",
            end_date="2024-03-15 23:59:59",
            is_holiday=True
        )

        start = date(2024, 3, 1)
        end = date(2024, 3, 31)
        working_days = self.calendar.get_working_day_list(start, end)

        for day in range(11, 16):
            self.assertNotIn(date(2024, 3, day), working_days)

        # March 2024 has 21 weekdays; 5 of them fall inside the break
        self.assertEqual(self.calendar.get_working_days(start, end), 21 - 5)

    def test_get_holidays_overlap_before_window(self):
        """An event that starts before the queried window but overlaps into
        it should still be returned."""
        event = Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="Cross-month Break",
            start_date="2024-02-28 00:00:00",
            end_date="2024-03-05 23:59:59",
            is_holiday=True
        )

        holidays = self.calendar.get_holidays(date(2024, 3, 1), date(2024, 3, 31))
        self.assertIn(event.id, set(holidays.values_list('id', flat=True)))

    def test_get_events_overlap_before_window(self):
        """Non-holiday events overlapping the window from before it starts
        should also be returned by get_events."""
        event = Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="Sports Week",
            start_date="2024-02-28 00:00:00",
            end_date="2024-03-05 23:59:59",
            is_common=True
        )

        events = self.calendar.get_events(date(2024, 3, 1), date(2024, 3, 31))
        self.assertIn(event.id, set(events.values_list('id', flat=True)))

    def test_get_events(self):
        """Test fetching all events in a date range"""
        event1 = Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="School Assembly",
            start_date="2024-01-10 00:00:00",
            end_date="2024-01-10 23:59:59",
            is_common=True
        )
        event2 = Event.objects.create(
            tenant=self.tenant,
            academic_year=self.academic_year,
            title="Sports Day",
            start_date="2024-01-15 00:00:00",
            end_date="2024-01-15 23:59:59",
            is_common=True
        )

        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        events = self.calendar.get_events(start, end)

        self.assertEqual(events.count(), 2)
        event_ids = set(events.values_list('id', flat=True))
        self.assertIn(event1.id, event_ids)
        self.assertIn(event2.id, event_ids)
