"""
Role resolution — the single black box that maps a ``User`` to their portal roles.

The rest of the portal (permissions, serializers, views) depends ONLY on the
contract exposed here, never on how a role is derived. Today roles are inferred
from which profile models (Guardian / Employee / Student) are linked to the user
and whether the employee has an active library assignment; if that ever changes
(e.g. an explicit ``role`` column), only this module needs to be rewritten.

A single account may hold several roles at once — a teacher who is also a parent,
a teacher who is also a librarian, etc. ``resolve_roles`` returns the full set;
each portal endpoint still scopes itself to one role and gets the matching
profile via :meth:`RoleSet.context_for`.

Contract:
    resolve_roles(user) -> RoleSet
    RoleSet.roles            -> frozenset of ROLE_* constants
    RoleSet.primary          -> the highest-priority role (or ROLE_UNKNOWN)
    RoleSet.has(role)        -> bool
    RoleSet.is_portal_user   -> holds at least one portal role
    RoleSet.profile_for(role)-> the Guardian/Employee/Student backing that role
    RoleSet.context_for(role)-> RoleContext(role, profile_for(role))

    resolve_role(user) -> RoleContext   (deprecated single-role shim)
    RoleContext.role / .profile / .is_parent / .is_teacher / ...
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

ROLE_ADMIN = "admin"
ROLE_HR = "hr"
ROLE_TEACHER = "teacher"
ROLE_LIBRARIAN = "librarian"
ROLE_PARENT = "parent"
ROLE_STUDENT = "student"
ROLE_UNKNOWN = "unknown"

# Roles allowed to sign in to this portal. Admins use the main Django app.
PORTAL_ROLES = {ROLE_PARENT, ROLE_TEACHER, ROLE_LIBRARIAN, ROLE_HR}

# Highest priority first. Drives ``primary`` (default landing experience) and the
# order roles are listed in.
ROLE_PRIORITY = [
    ROLE_HR,
    ROLE_LIBRARIAN,
    ROLE_TEACHER,
    ROLE_PARENT,
    ROLE_STUDENT,
    ROLE_ADMIN,
]

# HR permission codenames (see ``core.authz.registry``). A linked, active employee
# whose user holds any of these — or any ``hr.*`` / ``reports.hr*`` code — resolves
# to the ``hr`` portal role.
_HR_CODENAME_PREFIXES = ("hr.", "reports.hr")


@dataclass(frozen=True)
class RoleContext:
    """A single role plus the profile that backs it, for one endpoint."""

    role: str
    profile: object = None  # Guardian | Employee | Student | None

    @property
    def is_parent(self) -> bool:
        return self.role == ROLE_PARENT

    @property
    def is_teacher(self) -> bool:
        return self.role == ROLE_TEACHER

    @property
    def is_hr(self) -> bool:
        return self.role == ROLE_HR

    @property
    def is_librarian(self) -> bool:
        return self.role == ROLE_LIBRARIAN

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_portal_user(self) -> bool:
        return self.role in PORTAL_ROLES


@dataclass(frozen=True)
class RoleSet:
    """Every role a user holds, with the profile object for each."""

    roles: frozenset = field(default_factory=frozenset)
    employee: object = None
    guardian: object = None
    student: object = None

    def has(self, role: str) -> bool:
        return role in self.roles

    @property
    def primary(self) -> str:
        for role in ROLE_PRIORITY:
            if role in self.roles:
                return role
        return ROLE_UNKNOWN

    @property
    def is_portal_user(self) -> bool:
        return bool(self.roles & PORTAL_ROLES)

    def profile_for(self, role: str) -> Optional[object]:
        if role in (ROLE_TEACHER, ROLE_LIBRARIAN, ROLE_HR):
            return self.employee
        if role == ROLE_PARENT:
            return self.guardian
        if role == ROLE_STUDENT:
            return self.student
        return None

    def context_for(self, role: str) -> RoleContext:
        return RoleContext(role, self.profile_for(role))

    def ordered(self) -> list:
        """Roles held, highest priority first."""
        return [r for r in ROLE_PRIORITY if r in self.roles]


def _linked(user, attr) -> Optional[object]:
    """Safely follow a reverse OneToOne relation that may not exist."""
    try:
        return getattr(user, attr)
    except Exception:
        return None


def _current_tenant():
    """The tenant for the active DB schema (set by django-tenants middleware)."""
    try:
        from django.db import connection

        return getattr(connection, "tenant", None)
    except Exception:
        return None


def hr_permissions_for(user, tenant=None) -> frozenset:
    """The HR-scoped codenames a user holds in ``tenant`` (or the current one).

    Used both to decide the ``hr`` role and to tell the frontend which HR
    sections to show. Returns an empty set on any failure (RBAC not migrated,
    no tenant, ...).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()
    tenant = tenant or _current_tenant()
    if tenant is None:
        return frozenset()
    try:
        from core.authz.access import get_permission_set

        granted = get_permission_set(user, tenant)
    except Exception:
        return frozenset()
    return frozenset(
        c for c in granted if c.startswith(_HR_CODENAME_PREFIXES)
    )


def resolve_roles(user) -> RoleSet:
    """
    Resolve every portal role a user holds.

    - an active ``Employee`` link  -> ``teacher``
    - that employee also having an active ``LibraryStaff`` row -> ``librarian``
    - an active ``Guardian`` link  -> ``parent``
    - a ``Student`` link           -> ``student``
    - ``is_admin`` with no portal role -> ``admin`` (kept so admin-only accounts
      still resolve to something; an admin who is also staff/parent is treated as
      that portal role and ``admin`` is left off — the dashboard is separate).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return RoleSet(frozenset({ROLE_UNKNOWN}))

    roles: set = set()

    employee = _linked(user, "employee")
    if employee is not None and getattr(employee, "status", True):
        roles.add(ROLE_TEACHER)
        try:
            if employee.library_assignments.filter(
                is_active=True, library__is_active=True
            ).exists():
                roles.add(ROLE_LIBRARIAN)
        except Exception:
            pass
        if hr_permissions_for(user):
            roles.add(ROLE_HR)
    else:
        employee = None

    guardian = _linked(user, "guardian")
    if guardian is not None and getattr(guardian, "is_active", True):
        roles.add(ROLE_PARENT)
    else:
        guardian = None

    student = _linked(user, "student")
    if student is not None:
        roles.add(ROLE_STUDENT)
    else:
        student = None

    if not (roles & PORTAL_ROLES) and getattr(user, "is_admin", False):
        roles.add(ROLE_ADMIN)

    if not roles:
        roles.add(ROLE_UNKNOWN)

    return RoleSet(frozenset(roles), employee=employee, guardian=guardian, student=student)


def resolve_role(user) -> RoleContext:
    """Deprecated single-role shim. Prefer :func:`resolve_roles`.

    Returns the highest-priority role and its profile so older call sites keep
    working during the multi-role rollout.
    """
    roleset = resolve_roles(user)
    return roleset.context_for(roleset.primary)
