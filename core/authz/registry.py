"""The permission registry — the single source of truth for what access
codenames exist in the system.

CANONICAL NAMING CONVENTION (as of Phase 2.1):
  Format: "<domain>.<resource>.<action>"
  - domain: plural (e.g., hr, finance, admissions, not academic)
  - resource: plural (e.g., employees, invoices, not employee, invoice)
  - action: view/manage/specific (e.g., view, manage, approve, conduct)

ENFORCEMENT:
  - All NEW endpoints in core/api/*.py use DRF API codenames (lines 93-167)
  - Legacy codenames (lines 39-91) are DEPRECATED but kept for backward compatibility
  - New work MUST use DRF API codenames; see "DRF API layer" section below
  - Role editor UI renders both sections but should phase out legacy over time

DRIFT RESOLVED IN PHASE 2.1:
  - hr.employee.* (legacy singular) → hr.employees.* (canonical plural)
  - academic.* → academics.* (canonical plural domain name)
  - transport.view (generic) → transport.routes/stops/staff/fees.* (specific resources)
  - All new serializers in Phase 2.1 use DRF API codenames exclusively
"""
from __future__ import annotations

from collections import OrderedDict

# module key -> human label (declaration order = display order)
MODULES: "OrderedDict[str, str]" = OrderedDict([
    ("hr", "Human Resources"),
    ("finance", "Finance"),
    ("academic", "Academic"),
    ("academics", "Academics (API)"),
    ("transport", "Transport"),
    ("admissions", "Admissions"),
    ("hostel", "Hostel"),
    ("library", "Library"),
    ("students", "Students"),
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

    # =========================================================================
    # DRF API layer — codenames actually checked by core/api/*.py ViewSets via
    # core.authz.drf.HasPermission(read=..., write=...). These were missing
    # from this registry entirely until 2026-09-12, which meant no role could
    # ever grant access to them (silently filtered out by ALL_CODENAMES) and
    # only is_root users could use these endpoints. See module docstring.
    # =========================================================================

    # --- Students (API) ------------------------------------------------
    ("students.view", "View students"),
    ("students.manage", "Create, edit & deactivate students"),

    # --- Academics (API) -------------------------------------------------
    ("academics.batches.view", "View batches"),
    ("academics.batches.manage", "Create & edit batches"),
    ("academics.courses.view", "View courses"),
    ("academics.courses.manage", "Create & edit courses"),
    ("academics.subjects.view", "View subjects"),
    ("academics.subjects.manage", "Create & edit subjects"),

    # --- Finance (API) ---------------------------------------------------
    ("finance.invoices.view", "View invoices"),
    ("finance.transactions.view", "View finance transactions"),
    ("finance.transactions.manage", "Record & edit finance transactions"),
    ("finance.student-fees.view", "View student fee balances"),
    ("finance.student-fees.manage", "Manage student fee assignments"),
    ("finance.discounts.view", "View fee discounts"),
    ("finance.discounts.manage", "Create & edit fee discounts"),
    ("finance.fines.view", "View fee fine slabs"),
    ("finance.fines.manage", "Create & edit fee fine slabs"),

    # --- HR (API) ----------------------------------------------------------
    ("hr.employees.view", "View employees"),
    ("hr.employees.manage", "Create, edit & deactivate employees"),
    ("hr.qualifications.view", "View employee qualifications"),
    ("hr.qualifications.manage", "Manage employee qualifications"),
    ("hr.documents.view", "View employee documents"),
    ("hr.documents.manage", "Manage employee documents"),
    ("hr.contracts.view", "View employee contracts"),
    ("hr.contracts.manage", "Manage employee contracts"),
    ("hr.leave-types.view", "View leave types"),
    ("hr.leave-types.manage", "Manage leave types"),
    ("hr.leave-requests.view", "View leave requests"),
    ("hr.leave-requests.manage", "Create & edit leave requests"),
    ("hr.leave-requests.approve", "Approve or reject leave requests"),
    ("hr.attendance.view", "View staff attendance"),
    ("hr.attendance.manage", "Mark & edit staff attendance"),
    ("hr.reviews.view", "View performance reviews"),
    ("hr.reviews.manage", "Conduct & record performance reviews"),
    ("hr.training.view", "View staff training records"),
    ("hr.training.manage", "Record & manage staff training"),
    ("hr.exit.view", "View staff exit records"),
    ("hr.exit.manage", "Manage staff exit & offboarding"),

    # --- Admissions (API) --------------------------------------------------
    ("admissions.application.view", "View admission applications (API)"),
    ("admissions.application.manage", "Process admission applications (API)"),
    ("admissions.enquiry.view", "View applicant enquiries (API)"),
    ("admissions.enquiry.manage", "Manage applicant enquiries (API)"),

    # --- Hostel (API) --------------------------------------------------
    ("hostel.rooms.view", "View hostel rooms"),
    ("hostel.rooms.manage", "Manage hostel rooms"),
    ("hostel.fees.view", "View hostel fees"),
    ("hostel.fees.manage", "Manage hostel fees"),

    # --- Transport (API) -----------------------------------------------
    ("transport.routes.view", "View transport routes"),
    ("transport.routes.manage", "Manage transport routes"),
    ("transport.stops.view", "View route stops"),
    ("transport.stops.manage", "Manage route stops"),
    ("transport.staff.view", "View transport staff"),
    ("transport.staff.manage", "Manage transport staff"),
    ("transport.fees.view", "View transport fees"),
    ("transport.fees.manage", "Manage transport fees"),

    # --- Library (API) -------------------------------------------------
    ("library.view", "View library book catalog"),
    ("library.manage", "Manage library book catalog"),
    ("library.config.view", "View library configuration"),
    ("library.config.manage", "Manage library configuration"),
    ("library.staff.view", "View library staff"),
    ("library.staff.manage", "Manage library staff"),
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
