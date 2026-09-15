"""Shared tenant (school) provisioning logic.

Single source of truth for creating a School (tenant), its domains, and an
optional superuser. Both the ``create_initial_tenant`` and ``provision_tenant``
management commands call into this module so the logic lives in one place.

These functions operate on the **public** schema models (School / Domain) plus
the per-tenant User, so they are plain functions rather than a
``TenantAwareService`` subclass.

Notes on django-tenants:
- ``School.auto_create_schema = True`` means ``School.objects.create()`` already
  creates the Postgres schema *and* runs tenant migrations. There is therefore
  no need (and it would be redundant) to call ``migrate`` again afterwards.
- ``School.save()`` runs migrations during the save, so it must NOT be wrapped in
  an outer ``transaction.atomic`` block. Cleanup of a partially-provisioned
  tenant is handled explicitly via :func:`_destroy_school`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from django.db import connection
from django_tenants.utils import schema_exists, tenant_context

from core.models import School, Domain, User
from .exceptions import DuplicateException, ServiceException

logger = logging.getLogger(__name__)


@dataclass
class ProvisionResult:
    """Outcome of :func:`provision_school` — lets callers report what happened."""

    school: School
    school_created: bool
    primary_domain_created: bool = False
    extra_domains_created: list[str] = field(default_factory=list)
    country_warning: Optional[str] = None


def _normalize_domain(domain: str) -> str:
    """Lowercase, strip protocol and trailing slash from a domain string."""
    domain = domain.strip().lower()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.rstrip("/")


def _resolve_country(country_code: Optional[str]) -> tuple[object, Optional[str]]:
    """Look up a Country by code. Returns (country_or_None, warning_or_None).

    A missing/unknown code is a soft failure: the tenant is still created without
    a country, and the warning is surfaced to the caller.
    """
    if not country_code:
        return None, None
    try:
        from core.models import Country
        return Country.objects.get(code__iexact=country_code), None
    except Exception:
        return None, (
            f"Country code '{country_code}' not found — creating tenant without country."
        )


def _destroy_school(school: School) -> None:
    """Drop a partially-provisioned tenant: its schema then its row.

    Used to roll back when a later step fails after the School (and its schema)
    were already created. ``School`` has no ``auto_drop_schema``, so the schema
    is dropped explicitly here to avoid orphaned schemas.
    """
    schema_name = school.schema_name
    try:
        if schema_exists(schema_name):
            with connection.cursor() as cursor:
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
    except Exception:
        logger.exception("Failed to drop schema '%s' during cleanup", schema_name)
    try:
        School.objects.filter(pk=school.pk).delete()
    except Exception:
        logger.exception("Failed to delete School row '%s' during cleanup", schema_name)


def provision_school(
    *,
    name: str,
    code: str,
    schema_name: str,
    domain: str,
    is_active: bool = True,
    extra_domains: Optional[list[str]] = None,
    country_code: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    website: Optional[str] = None,
    address_line1: Optional[str] = None,
    city: Optional[str] = None,
    allow_existing: bool = False,
) -> ProvisionResult:
    """Create a School (tenant) with a primary domain and optional extra domains.

    Guards against duplicate schema / code / domain up front to shrink the
    partial-failure window. If the school already exists and ``allow_existing``
    is True, the existing school is returned with ``school_created=False`` (used
    by ``create_initial_tenant``); otherwise a :class:`DuplicateException` is
    raised.

    On failure after the school is created, the schema and row are cleaned up.
    """
    schema_name = schema_name.lower().strip()
    domain = _normalize_domain(domain)

    existing = School.objects.filter(schema_name=schema_name).first()
    if existing is not None:
        if allow_existing:
            return ProvisionResult(school=existing, school_created=False)
        raise DuplicateException(
            f"A tenant with schema_name '{schema_name}' already exists.",
            details={"schema_name": schema_name},
        )

    if School.objects.filter(code=code).exists():
        raise DuplicateException(
            f"A tenant with code '{code}' already exists.",
            details={"code": code},
        )

    if Domain.objects.filter(domain=domain).exists():
        raise DuplicateException(
            f"Domain '{domain}' is already registered.",
            details={"domain": domain},
        )

    country, country_warning = _resolve_country(country_code)

    # Create the School. auto_create_schema=True creates + migrates the schema.
    try:
        school = School.objects.create(
            name=name,
            code=code,
            schema_name=schema_name,
            phone=phone,
            email=email,
            website=website,
            address_line1=address_line1,
            city=city,
            country=country,
            is_active=is_active,
        )
    except Exception as exc:
        logger.exception("Failed to create school '%s'", schema_name)
        raise ServiceException(f"Failed to create school: {exc}", original_exception=exc) from exc

    result = ProvisionResult(
        school=school,
        school_created=True,
        country_warning=country_warning,
    )

    # Domains. If anything fails here, roll back the freshly-created tenant.
    try:
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        result.primary_domain_created = True

        for extra in extra_domains or []:
            extra = _normalize_domain(extra)
            if not extra:
                continue
            Domain.objects.create(domain=extra, tenant=school, is_primary=False)
            result.extra_domains_created.append(extra)
    except Exception as exc:
        logger.exception("Failed to create domains for '%s'; rolling back tenant", schema_name)
        _destroy_school(school)
        raise ServiceException(
            f"Failed to create domains: {exc}", original_exception=exc
        ) from exc

    # Seed RBAC system roles inside the new tenant's schema. A failure here is
    # non-fatal — the roles can be (re)created later with `manage.py seed_roles`.
    try:
        from core.management.commands.seed_roles import seed_roles_for_tenant

        with tenant_context(school):
            seed_roles_for_tenant(school)
    except Exception:
        logger.exception("Failed to seed RBAC roles for '%s' (non-fatal)", schema_name)

    return result


def provision_default_modules(school: School) -> int:
    """Create a SchoolModule row for every registered module key, disabled by
    default. Mirrors ``core.admin.tenant._provision_all_modules`` and
    ``manage.py provision_school_modules`` — an operator still has to
    explicitly enable only what the school's agreement covers. Existing rows
    are left untouched. Returns the number of rows created."""
    from core.models import SchoolModule
    from core.modules import MODULES

    created = 0
    for module_key in MODULES.keys():
        _, was_created = SchoolModule.objects.get_or_create(
            school=school, module=module_key, defaults={"enabled": False}
        )
        if was_created:
            created += 1
    return created


def create_tenant_superuser(
    school: School,
    *,
    username: str,
    email: Optional[str],
    password: str,
    first_name: str,
    last_name: str,
) -> tuple[User, bool]:
    """Create an admin user inside the tenant's schema. Idempotent on username.

    Returns (user, created). If a user with ``username`` already exists in the
    schema, it is returned with ``created=False``.
    """
    if not password:
        raise ServiceException("A password is required to create a superuser.")

    with tenant_context(school):
        existing = User.objects.filter(username=username).first()
        if existing is not None:
            return existing, False

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_admin=True,
            is_root=True,  # provisioned owner account — full RBAC bypass
            is_active=True,
        )
        user.set_password(password)
        user.save()
        user.tenants.add(school)
        return user, True
