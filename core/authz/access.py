"""The one place authorization is computed.

``get_permission_set(user, tenant)`` -> the frozenset of codenames a user holds
in a tenant. ``has_permission(...)`` is the boolean convenience wrapper.

Resolution:
  * anonymous / no tenant                -> empty set
  * ``user.is_root``                      -> every codename (break-glass owner)
  * otherwise -> union of codenames from the user's active role assignments

Note: ``is_admin`` only gates *entry* to the dashboard (see
``core.middleware.DashboardAccessMiddleware``). Every dashboard user is
``is_admin``; what they can actually do is decided here, by their roles.

The result is cached on the request (``request._authz_cache``) when a request is
passed, so a view + its template + its decorator resolve it once.
"""
from __future__ import annotations

from .registry import ALL_CODENAMES


def _tenant_id(tenant):
    return getattr(tenant, "id", None) or getattr(tenant, "pk", None)


def _compute(user, tenant) -> "frozenset[str]":
    if user is None or not getattr(user, "is_authenticated", False):
        return frozenset()
    if tenant is None or _tenant_id(tenant) is None:
        return frozenset()
    if getattr(user, "is_root", False):
        return frozenset(ALL_CODENAMES)

    # Imported lazily: this module is imported from core.models-adjacent code.
    from core.models import RolePermission

    try:
        codenames = (
            RolePermission.objects.filter(
                tenant=tenant,
                role__is_active=True,
                role__assignments__user_id=user.id,
                role__assignments__is_active=True,
            )
            .values_list("codename", flat=True)
            .distinct()
        )
        return frozenset(c for c in codenames if c in ALL_CODENAMES)
    except Exception:
        # RBAC tables not migrated yet (e.g. a DB still on <=0138). Degrade to
        # "no role permissions" rather than 500 — `is_root` users are unaffected
        # since they short-circuit above.
        return frozenset()


def get_permission_set(user, tenant, request=None) -> "frozenset[str]":
    if request is not None:
        cache = getattr(request, "_authz_cache", None)
        if cache is None:
            cache = {}
            setattr(request, "_authz_cache", cache)
        key = (getattr(user, "id", None), _tenant_id(tenant))
        if key not in cache:
            cache[key] = _compute(user, tenant)
        return cache[key]
    return _compute(user, tenant)


def has_permission(user, tenant, codename, request=None) -> bool:
    return codename in get_permission_set(user, tenant, request=request)


def has_any_permission(user, tenant, codenames, request=None) -> bool:
    granted = get_permission_set(user, tenant, request=request)
    return any(c in granted for c in codenames)


def request_permission_set(request) -> "frozenset[str]":
    """Codenames for the logged-in user in the current request's tenant."""
    return get_permission_set(
        getattr(request, "user", None),
        getattr(request, "tenant", None),
        request=request,
    )
