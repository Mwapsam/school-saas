"""The permission registry — the single source of truth for what access
codenames exist in the system.

A codename is ``"<module>.<resource>.<action>"``. The role editor UI renders
checkboxes grouped by module, in the order declared here.

Enforcement status: the ``hr.*`` codenames are wired into real view/API gates
(see :mod:`core.authz.mixins`). The other modules are declared so roles can be
composed ahead of their gates being migrated off the legacy ``is_admin`` check;
until a given view is migrated, ``is_admin`` remains the effective gate there.
"""
from __future__ import annotations

from collections import OrderedDict

# module key -> human label (declaration order = display order)
MODULES: "OrderedDict[str, str]" = OrderedDict([
    ("hr", "Human Resources"),
    ("finance", "Finance"),
    ("academic", "Academic"),
    ("transport", "Transport"),
    ("admissions", "Admissions"),
    ("reports", "Reports"),
    ("settings", "Settings & Administration"),
])

# codename -> human label (declaration order = display order within a module)
PERMISSIONS: "OrderedDict[str, str]" = OrderedDict([
    # --- Human Resources ---------------------------------------------------
    ("hr.employee.view", "View staff records"),
    ("hr.employee.manage", "Add, edit & deactivate staff"),
    ("hr.contract.view", "View staff contracts"),
    ("hr.contract.manage", "Create, renew & end staff contracts"),
    ("hr.document.view", "View staff documents"),
    ("hr.document.manage", "Upload & manage staff documents"),
    ("hr.leave.view", "View leave requests & balances"),
    ("hr.leave.manage", "Record & edit leave requests"),
    ("hr.leave.approve", "Approve or reject leave"),
    ("hr.attendance.manage", "Mark & edit staff attendance"),
    ("hr.payroll.view", "View payroll & payslips"),
    ("hr.payroll.manage", "Manage payroll, generate & approve payslips"),
    ("hr.performance.view", "View performance reviews"),
    ("hr.performance.conduct", "Conduct & record performance reviews"),
    ("hr.training.view", "View staff training records"),
    ("hr.training.manage", "Record & manage staff training"),
    ("hr.recruitment.view", "View vacancies & applicants"),
    ("hr.recruitment.manage", "Manage recruitment & applicants"),
    ("hr.onboarding.view", "View onboarding checklists"),
    ("hr.onboarding.manage", "Manage staff onboarding"),
    ("hr.exit.view", "View staff exit records"),
    ("hr.exit.manage", "Manage staff exit & offboarding"),
    ("hr.disciplinary.view", "View disciplinary & grievance records"),
    ("hr.disciplinary.manage", "Manage disciplinary & grievance records"),
    ("hr.tasks.manage", "Manage HR tasks & reminders"),
    ("hr.settings.manage", "Manage HR settings (categories, positions, leave types)"),
    # --- Finance ---------------------------------------------------------
    ("finance.fees.view", "View fees & collections"),
    ("finance.fees.collect", "Collect fee payments"),
    ("finance.fees.manage", "Manage fee structures & assignments"),
    ("finance.invoices.manage", "Manage invoices & receipts"),
    # --- Academic ------------------------------------------------------
    ("academic.batches.manage", "Manage classes & batches"),
    ("academic.exams.manage", "Manage exams & grading"),
    ("academic.reports.manage", "Manage report cards"),
    ("academic.timetable.manage", "Manage timetables"),
    # --- Transport ---------------------------------------------------
    ("transport.view", "View transport routes, vehicles & assignments"),
    ("transport.manage", "Manage transport settings, fleet, routes & assignments"),
    # --- Admissions --------------------------------------------------
    ("admissions.applications.view", "View admission applications"),
    ("admissions.applications.manage", "Process admission applications"),
    # --- Reports ---------------------------------------------------
    ("reports.hr", "Access HR reports"),
    ("reports.hr.export", "Export HR reports (PDF / Excel)"),
    ("reports.finance", "Access finance reports"),
    ("reports.academic", "Access academic reports"),
    # --- Settings & Administration -------------------------------
    ("settings.users.manage", "Manage user logins & portal access"),
    ("settings.roles.manage", "Manage roles & permissions"),
    ("settings.school.manage", "Manage school configuration"),
])

ALL_CODENAMES = frozenset(PERMISSIONS)


def is_valid_codename(codename: str) -> bool:
    return codename in ALL_CODENAMES


def module_of(codename: str) -> str:
    return codename.split(".", 1)[0]


def expand(patterns) -> "frozenset[str]":
    """Expand a list of codenames / ``"module.*"`` / ``"*"`` wildcards into a
    concrete codename set. Unknown exact codenames are dropped (defensive —
    keeps a stale seed definition from crashing)."""
    out: set[str] = set()
    for p in patterns:
        if p == "*":
            return frozenset(ALL_CODENAMES)
        if p.endswith(".*"):
            prefix = p[:-1]  # keep the trailing dot
            out.update(c for c in ALL_CODENAMES if c.startswith(prefix))
        elif p in ALL_CODENAMES:
            out.add(p)
    return frozenset(out)


def permissions_by_module():
    """[(module_key, module_label, [(codename, label), ...]), ...] in display
    order — consumed by the role-editor template."""
    grouped: "OrderedDict[str, list]" = OrderedDict((k, []) for k in MODULES)
    for codename, label in PERMISSIONS.items():
        grouped.setdefault(module_of(codename), []).append((codename, label))
    return [
        (key, MODULES.get(key, key.title()), items)
        for key, items in grouped.items()
        if items
    ]
