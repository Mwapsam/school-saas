"""
List (and optionally fix) admin/staff accounts locked out of the dashboard
by the `is_admin` login gate added in core/forms.py (StaffOnlyAuthenticationForm).

That gate is new; `is_admin` existed long before it but was never required for
dashboard login, so any pre-existing staff account created without the
"Grant administrator access" checkbox (or via shell/seed data) now gets
rejected with "This account cannot access the staff dashboard...".

This command finds active, non-portal accounts (not linked to an Employee or
Guardian, mirroring the "standalone" classification in UserManagementView)
that have is_admin=False - the accounts most likely to be legitimate
dashboard staff caught by the new gate - and optionally grants them access.

Usage:
    # List candidates across all tenants
    python manage.py list_dashboard_lockouts

    # Grant dashboard access to specific accounts after review
    python manage.py list_dashboard_lockouts --grant alice bob
"""

from django.core.management.base import BaseCommand

from core.models import User, Employee, Guardian
from core.services.logging_service import ServiceLogger


class Command(BaseCommand):
    help = "List active non-portal accounts with is_admin=False (likely locked out of the dashboard by the new login gate), and optionally grant them access."

    def add_arguments(self, parser):
        parser.add_argument(
            "--grant", nargs="+", metavar="USERNAME", default=None,
            help="Set is_admin=True for these usernames instead of listing candidates.",
        )

    def handle(self, *args, **options):
        grant = options["grant"]
        if grant:
            self._grant(grant)
        else:
            self._list()

    def _portal_linked_user_ids(self):
        ids = set(Employee.objects.exclude(user=None).values_list("user_id", flat=True))
        ids |= set(Guardian.objects.exclude(user=None).values_list("user_id", flat=True))
        return ids

    def _list(self):
        candidates = (
            User.objects.filter(is_active=True, is_admin=False)
            .exclude(id__in=self._portal_linked_user_ids())
            .order_by("username")
        )

        if not candidates:
            self.stdout.write(self.style.SUCCESS("No locked-out dashboard accounts found."))
            return

        self.stdout.write(f"Found {candidates.count()} candidate account(s):\n")
        for u in candidates:
            tenants = ", ".join(t.name for t in u.tenants.all()) or "(none)"
            last_login = u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "never"
            self.stdout.write(
                f"  {u.username:<25} {u.email or '':<30} tenants=[{tenants}] "
                f"last_login={last_login} created={u.created_at:%Y-%m-%d}"
            )

        self.stdout.write(
            self.style.WARNING(
                "\nReview the list above, then run with --grant <username> [<username> ...] "
                "to restore dashboard access for the ones that are legitimate staff."
            )
        )

    def _grant(self, usernames):
        # Bypasses UserService.update_user's "only an admin can grant is_admin"
        # check on purpose: this command is the one-time bootstrap for accounts
        # that predate the login gate and have no existing admin to perform the
        # grant through the app. Still goes through the same audit log.
        logger = ServiceLogger("user")

        for username in usernames:
            user = User.objects.filter(username=username).first()
            if not user:
                self.stdout.write(self.style.ERROR(f"  {username}: not found"))
                continue
            if user.is_admin:
                self.stdout.write(f"  {username}: already is_admin=True, skipping")
                continue

            user.is_admin = True
            user.save(update_fields=["is_admin"])
            logger.log_update(
                resource_type="user",
                resource_id=str(user.id),
                changed_fields={"is_admin": {"old": False, "new": True}},
            )
            self.stdout.write(self.style.SUCCESS(f"  {username}: granted dashboard access"))
