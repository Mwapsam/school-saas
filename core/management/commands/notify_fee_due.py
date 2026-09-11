"""Notify guardians of students with overdue fee balances.

For each tenant, reads the live defaulters list (``DefaultersService``) and
dispatches a ``fee_due`` notification per defaulting student through Notification
Control (Configuration -> Notification Control). Sends nothing unless the school
enabled a channel for ``(fee_due, guardians)``.

Idempotent within a 7-day window: a student notified in the last 7 days is
skipped (tracked via ``ConfigStore`` key ``fee_due_last_notified:<student_id>``),
so a daily schedule does not spam.

Usage:
    python manage.py notify_fee_due
    python manage.py notify_fee_due --tenant-id <school_id>
    python manage.py notify_fee_due --as-of 2025-03-01
    python manage.py notify_fee_due --dry-run
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import ConfigStore, School, StudentGuardianRelation
from core.services.defaulters_service import DefaultersService
from core.services.notification_service import NotificationService

RESEND_AFTER_DAYS = 7


class Command(BaseCommand):
    help = "Dispatch fee_due notifications to guardians of defaulting students."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", help="Limit to a single School/tenant id")
        parser.add_argument("--as-of", help="Evaluate overdue against this date (YYYY-MM-DD)")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Print who would be notified without sending or recording anything",
        )

    def handle(self, *args, **options):
        as_of = date.fromisoformat(options["as_of"]) if options.get("as_of") else date.today()
        dry_run = options.get("dry_run", False)

        schools = School.objects.all()
        if options.get("tenant_id"):
            schools = schools.filter(id=options["tenant_id"])

        grand_total = 0
        for school in schools:
            report = DefaultersService(school).list_defaulters(as_of=as_of)
            store = ConfigStore(school)
            cutoff = as_of - timedelta(days=RESEND_AFTER_DAYS)
            sent = 0

            for row in report["student_rows"]:
                student = row.student
                key = f"fee_due_last_notified:{student.id}"
                last = store.get(key)
                if last:
                    try:
                        if date.fromisoformat(last) > cutoff:
                            continue
                    except ValueError:
                        pass

                relations = (
                    StudentGuardianRelation.objects
                    .filter(tenant=school, student=student)
                    .select_related("guardian")
                )
                recipients = [
                    {
                        "id": r.guardian_id, "type": "guardian",
                        "phone": getattr(r.guardian, "mobile_phone", None),
                        "email": getattr(r.guardian, "email", None),
                    }
                    for r in relations if r.guardian_id
                ]
                if not recipients:
                    continue

                msg = (
                    f"A fee balance of {row.outstanding} for {row.student_name} is "
                    f"overdue by {row.max_days_overdue} day(s). Please settle it at "
                    f"your earliest convenience."
                )
                if dry_run:
                    self.stdout.write(
                        f"[{school.code}] {row.student_name}: {row.outstanding} "
                        f"({row.max_days_overdue}d) -> {len(recipients)} guardian(s)"
                    )
                else:
                    NotificationService(school).dispatch(
                        "fee_due", "guardians", recipients,
                        title="Fee payment overdue", message=msg,
                    )
                    store.set(key, as_of.isoformat())
                sent += 1

            if sent:
                grand_total += sent
                self.stdout.write(self.style.SUCCESS(
                    f"{school.code}: {'(dry-run) ' if dry_run else ''}{sent} student(s) notified"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"Done. {grand_total} student notification(s){' (dry-run)' if dry_run else ''}."
        ))
