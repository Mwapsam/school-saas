"""HR audit trail — one call to record a who-changed-what row.

``record_hr_audit`` is deliberately tiny and forgiving: an audit write must
never break the mutation it is recording, so every failure is swallowed (and
logged) rather than raised. Read the trail through :class:`core.models.HRAuditLog`.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("core.services.hr_audit")


def _label_for(actor) -> str:
    if actor is None:
        return "system"
    name = (
        getattr(actor, "get_full_name", lambda: "")()
        or getattr(actor, "username", "")
        or getattr(actor, "email", "")
    )
    return str(name or getattr(actor, "id", "") or "unknown")


def _stringify(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def record_hr_audit(
    tenant,
    *,
    actor=None,
    action: str,
    target_type: str,
    target_id: Any = "",
    field: str = "",
    old_value: Any = None,
    new_value: Any = None,
    detail: Optional[dict] = None,
):
    """Write one :class:`core.models.HRAuditLog` row.

    ``actor`` is a ``User`` (or ``None`` for system actions). ``target_type`` is a
    short label like ``"employee"`` / ``"contract"``. Returns the created row or
    ``None`` on failure.
    """
    from core.models import HRAuditLog

    try:
        return HRAuditLog.objects.create(
            tenant=tenant,
            actor_id=getattr(actor, "id", None),
            actor_label=_label_for(actor),
            action=action,
            target_type=target_type,
            target_id=str(target_id or ""),
            field=field or "",
            old_value=_stringify(old_value),
            new_value=_stringify(new_value),
            detail=detail,
        )
    except Exception:  # pragma: no cover - audit must never break the caller
        logger.exception(
            "record_hr_audit failed (action=%s target=%s:%s)",
            action, target_type, target_id,
        )
        return None
