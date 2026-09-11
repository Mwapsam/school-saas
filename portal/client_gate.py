"""X-Client-App header gate (Configuration → Manage Clients).

A request may identify its client app with two headers:

    X-Client-App:          <ClientApp.slug>     e.g. "pinewood-parent-android"
    X-Client-App-Version:  <semver-ish>         e.g. "1.4.0"

Rules (all opt-out — an unknown or header-less client is always allowed, so the
web app and curl keep working until a school explicitly registers + disables a
client):

  * slug matches a ClientApp row with is_enabled=False  -> 403 client_disabled
  * version < ClientApp.min_supported_version           -> 426 upgrade_required

A matched, allowed client has its ``last_seen_at`` stamped (best-effort).
"""
from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

log = logging.getLogger("portal.audit")


def _parse_version(value: str) -> tuple:
    parts = []
    for chunk in (value or "").strip().split("."):
        num = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts) or (0,)


def check_client_app(request):
    """Return a DRF ``Response`` to short-circuit with, or ``None`` to proceed."""
    slug = (request.headers.get("X-Client-App") or "").strip()
    if not slug:
        return None

    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return None

    from core.models import ClientApp

    try:
        client = ClientApp.objects.filter(tenant=tenant, slug=slug).first()
    except Exception:  # table missing on an un-migrated tenant
        return None
    if client is None:
        return None

    if not client.is_enabled:
        log.warning("portal client blocked: tenant=%s slug=%s", tenant.id, slug)
        return Response(
            {"detail": f"The {client.name} app has been disabled by your school.",
             "code": "client_disabled"},
            status=status.HTTP_403_FORBIDDEN,
        )

    version = request.headers.get("X-Client-App-Version")
    if version and client.min_supported_version:
        if _parse_version(version) < _parse_version(client.min_supported_version):
            return Response(
                {"detail": "Please update to the latest version to continue.",
                 "code": "upgrade_required",
                 "min_supported_version": client.min_supported_version},
                status=426,  # Upgrade Required
            )

    try:
        ClientApp.objects.filter(pk=client.pk).update(last_seen_at=timezone.now())
    except Exception:
        pass
    return None
