"""
Single source of truth for attendance status semantics.

The Attendance model stores two half-day booleans (forenoon/afternoon) plus a
free-text reason. Both the admin dashboard and the teacher portal need to
translate that storage shape into a friendly status vocabulary and back --
these functions are the one place that translation happens.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

STATUS_PRESENT = "present"
STATUS_ABSENT = "absent"
STATUS_LATE = "late"
STATUS_HALF_DAY = "half_day"
STATUS_UNMARKED = "unmarked"
STATUS_FUTURE = "future"
STATUS_NON_SCHOOL_DAY = "non_school_day"

ATTENDANCE_STATUSES = (STATUS_PRESENT, STATUS_ABSENT, STATUS_LATE, STATUS_HALF_DAY)

_LATE_TAG = "Late arrival"

NOT_SCHOOL_DAY_MESSAGE = (
    "{date} is not a school day (holiday or non-working day). "
    "Attendance cannot be marked for this date."
)

LOCKED_MESSAGE = (
    "{date} is locked for attendance changes. "
    "Attendance can no longer be marked or edited for this date."
)

NO_ACTIVE_TERM_MESSAGE = (
    "{date} falls outside any active term. "
    "Attendance cannot be marked until the next term begins."
)


def status_from_record(record) -> str:
    """Map an Attendance row (or None) to a friendly status string.

    A missing row is treated as present -- this is the "premarked present"
    default: attendance is assumed present until an exception is recorded.
    """
    if record is None:
        return STATUS_PRESENT
    present = record.forenoon and record.afternoon
    if present and record.reason and "late" in record.reason.lower():
        return STATUS_LATE
    if present:
        return STATUS_PRESENT
    if record.forenoon or record.afternoon:
        return STATUS_HALF_DAY
    return STATUS_ABSENT


def fields_for_status(status: str, reason: Optional[str] = None) -> dict:
    """Return the Attendance field values that represent a status."""
    if status == STATUS_PRESENT:
        return {"forenoon": True, "afternoon": True, "reason": reason or None}
    if status == STATUS_LATE:
        return {"forenoon": True, "afternoon": True, "reason": reason or _LATE_TAG}
    if status == STATUS_HALF_DAY:
        return {"forenoon": True, "afternoon": False, "reason": reason or None}
    # absent
    return {"forenoon": False, "afternoon": False, "reason": reason or None}


def cell_status_for_day(
    record,
    day: date,
    today: date,
    is_school_day: bool,
) -> str:
    """Status for a single grid cell, accounting for future/non-school days.

    Unlike status_from_record, a missing row does not imply "present" when
    the day is in the future or isn't a school day -- those cases have
    nothing to imply presence about.
    """
    if day > today:
        return STATUS_FUTURE
    if not is_school_day:
        return STATUS_NON_SCHOOL_DAY
    return status_from_record(record)
