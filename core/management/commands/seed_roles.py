"""Seed the per-tenant system roles used by the RBAC layer.

Idempotent: creates missing system roles and reconciles their permission sets
to the definitions below (leaving custom, non-system roles untouched). Safe to
re-run after adding a permission to an existing system role.

Usage:
    python manage.py seed_roles --all
    python manage.py seed_roles --tenant=<school_id>
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.authz.registry import expand
from core.models import Role, RolePermission, School

# slug -> (display name, description, permission patterns)
SYSTEM_ROLES = {
    "super-admin": (
        "Super Admin",
        "Full access to every module. Equivalent to a legacy admin account.",
        ["*"],
    ),
    "hr-manager": (
        "HR Manager",
        "Full access to staff records, leave, attendance and payroll.",
        ["hr.*", "reports.hr", "reports.hr.export", "settings.users.manage"],
    ),
    "hr-officer": (
        "HR Officer",
        "Day-to-day HR: staff records, leave recording and attendance. No payroll, no approvals.",
        [
            "hr.employee.view", "hr.employee.manage",
            "hr.contract.view", "hr.document.view", "hr.document.manage",
            "hr.leave.view", "hr.leave.manage", "hr.attendance.manage",
            "hr.performance.view", "hr.training.manage",
            "hr.onboarding.manage", "hr.tasks.manage",
            "reports.hr",
        ],
    ),
    "finance": (
        "Finance",
        "Fee collection, invoicing and finance reporting.",
        ["finance.*", "reports.finance"],
    ),
    "academic-admin": (
        "Academic Admin",
        "Classes, exams, timetables and report cards.",
        ["academic.*", "reports.academic"],
    ),
    "front-office": (
        "Front Office",
        "Admissions processing and read-only staff directory.",
        ["admissions.*", "hr.employee.view"],
    ),
}


class Command(BaseCommand):
    help = "Seed / reconcile per-tenant system roles for RBAC"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=str, help="School ID to seed")
        parser.add_argument("--all", action="store_true", help="Seed every school")

    def handle(self, *args, **options):
        if options["all"]:
            tenants = list(School.objects.all())
        elif options["tenant"]:
            tenants = list(School.objects.filter(id=options["tenant"]))
            if not tenants:
                self.stderr.write(self.style.ERROR(f"School {options['tenant']} not found"))
                return
        else:
            self.stderr.write(self.style.ERROR("Pass --all or --tenant=<id>"))
            return

        for tenant in tenants:
            created, reconciled = seed_roles_for_tenant(tenant)
            self.stdout.write(
                f"{tenant.name}: {created} role(s) created, {reconciled} permission set(s) reconciled"
            )
        self.stdout.write(self.style.SUCCESS("✓ System roles seeded"))


def seed_roles_for_tenant(tenant) -> tuple[int, int]:
    """Create/reconcile the system roles for one tenant. Returns
    ``(roles_created, permission_sets_reconciled)``. Import & call this from
    tenant provisioning so new schools get roles automatically."""
    created = 0
    reconciled = 0
    for slug, (name, description, patterns) in SYSTEM_ROLES.items():
        role, was_created = Role.objects.get_or_create(
            tenant=tenant,
            slug=slug,
            defaults={"name": name, "description": description, "is_system": True, "is_active": True},
        )
        if was_created:
            created += 1
        else:
            changed = []
            if not role.is_system:
                role.is_system = True
                changed.append("is_system")
            if role.description != description:
                role.description = description
                changed.append("description")
            if changed:
                role.save(update_fields=changed + ["updated_at"])

        wanted = expand(patterns)
        current = set(RolePermission.objects.filter(role=role).values_list("codename", flat=True))
        if current != wanted:
            RolePermission.objects.filter(role=role).exclude(codename__in=wanted).delete()
            RolePermission.objects.bulk_create(
                [RolePermission(tenant=tenant, role=role, codename=c) for c in wanted - current]
            )
            reconciled += 1
    return created, reconciled
