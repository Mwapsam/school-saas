"""``attendance_absent`` notification hook.

Attendance is written from three places that don't share a chokepoint
(``AttendanceService.mark_batch_attendance`` / ``.record_student_attendance`` and
the teacher-portal ``AttendanceRegisterView``). Each calls
:func:`notify_newly_absent` after its write, passing a snapshot of the rows as
they were *before* the write so we only notify guardians when a student newly
transitions into an absent state (not on every re-save of an already-absent day).

Best-effort: routed through :class:`core.services.notification_service.NotificationService`,
which itself no-ops unless the school enabled a channel for
``(attendance_absent, guardians)`` in Configuration -> Notification Control.
"""
from __future__ import annotations

import logging

from core.services.attendance_semantics import STATUS_ABSENT, status_from_record

log = logging.getLogger("core.notifications")


def _is_absent(forenoon, afternoon) -> bool:
    return not forenoon and not afternoon


def notify_newly_absent(tenant, batch, day, prior_by_student, new_records) -> None:
    """
    tenant           - School
    batch            - Batch the attendance belongs to (for the message)
    day              - the attendance date
    prior_by_student - {student_id (str): Attendance row | None} taken BEFORE the write
    new_records      - iterable of {"student_id", "forenoon", "afternoon"} just written
    """
    try:
        newly_absent = []
        for rec in new_records:
            sid = str(rec["student_id"])
            if not _is_absent(rec.get("forenoon"), rec.get("afternoon")):
                continue
            was = status_from_record(prior_by_student.get(sid))
            if was != STATUS_ABSENT:
                newly_absent.append(sid)

        if not newly_absent:
            return

        from core.models import StudentGuardianRelation
        from core.services.notification_service import NotificationService

        relations = (
            StudentGuardianRelation.objects
            .filter(tenant=tenant, student_id__in=newly_absent)
            .select_related("guardian", "student")
        )
        by_student = {}
        for rel in relations:
            if not rel.guardian_id:
                continue
            by_student.setdefault(rel.student_id, []).append(rel)

        svc = NotificationService(tenant)
        day_str = day.strftime("%d %b %Y") if hasattr(day, "strftime") else str(day)
        for student_id, rels in by_student.items():
            name = f"{rels[0].student.first_name} {rels[0].student.last_name}".strip()
            recipients = [
                {
                    "id": r.guardian_id, "type": "guardian",
                    "phone": getattr(r.guardian, "mobile_phone", None),
                    "email": getattr(r.guardian, "email", None),
                }
                for r in rels
            ]
            svc.dispatch(
                "attendance_absent", "guardians", recipients,
                title=f"{name} marked absent",
                message=f"{name} was marked absent on {day_str}.",
            )
    except Exception:
        log.exception("attendance_absent notification failed")
