"""Read helpers for the configuration module.

The configuration *screens* write directly through the ORM (same pattern as
``SchoolSettingsView`` / ``AttendanceLabelEditView``). This module is the
**read** side — the stable interface the rest of the app calls so it never has
to know how a given preference is stored.

    from core.services.configuration_service import (
        portal_feature_enabled, student_sort_order, apply_student_sort,
        is_student_exempt, terminology_map, notification_rule_for,
    )
"""
from __future__ import annotations

from core.models import (
    ConfigStore, PortalFeatureAccess, StudentExemption, TerminologyOverride,
    NotificationRule,
)

# --- General settings / sorting ------------------------------------------------

SORT_FIELDS = {
    "first_name": ["first_name", "last_name"],
    "last_name": ["last_name", "first_name"],
    "admission_no": ["admission_no"],
    "roll_number": ["class_roll_no"],
}
DEFAULT_SORT = "first_name"


def student_sort_order(tenant) -> str:
    value = ConfigStore(tenant).get("student_sort_order", DEFAULT_SORT)
    return value if value in SORT_FIELDS else DEFAULT_SORT


def apply_student_sort(queryset, tenant):
    """Order a ``Student`` (or ``BatchStudent__student``) queryset per config."""
    fields = SORT_FIELDS[student_sort_order(tenant)]
    prefix = "" if queryset.model.__name__ == "Student" else "student__"
    return queryset.order_by(*[f"{prefix}{f}" for f in fields])


# --- Portal feature access ---------------------------------------------------

def portal_feature_enabled(tenant, feature: str, default: bool = True) -> bool:
    row = PortalFeatureAccess.objects.filter(tenant=tenant, feature=feature).first()
    return row.is_enabled if row else default


def portal_feature_map(tenant) -> dict:
    stored = {
        r.feature: r.is_enabled
        for r in PortalFeatureAccess.objects.filter(tenant=tenant)
    }
    return {key: stored.get(key, True) for key, _ in PortalFeatureAccess.FEATURES}


# --- Exempted students -----------------------------------------------------

def is_student_exempt(tenant, student_id, exemption_type, academic_year=None) -> bool:
    qs = StudentExemption.objects.filter(
        tenant=tenant, student_id=student_id,
        exemption_type=exemption_type, is_active=True,
    )
    if academic_year is not None:
        from django.db.models import Q
        qs = qs.filter(Q(academic_year=academic_year) | Q(academic_year__isnull=True))
    return qs.exists()


def exempt_student_ids(tenant, exemption_type, academic_year=None) -> set:
    qs = StudentExemption.objects.filter(
        tenant=tenant, exemption_type=exemption_type, is_active=True,
    )
    if academic_year is not None:
        from django.db.models import Q
        qs = qs.filter(Q(academic_year=academic_year) | Q(academic_year__isnull=True))
    return set(qs.values_list("student_id", flat=True))


# --- Custom words --------------------------------------------------------

def terminology_map(tenant) -> dict:
    """``{"student": {"one": "Pupil", "many": "Pupils"}, ...}`` for active rows."""
    out = {}
    for row in TerminologyOverride.objects.filter(tenant=tenant, is_active=True):
        out[row.term.lower()] = {
            "one": row.replacement,
            "many": row.replacement_plural or f"{row.replacement}s",
        }
    return out


def custom_word(tenant, term: str, plural: bool = False) -> str:
    entry = terminology_map(tenant).get(term.lower())
    if entry:
        return entry["many" if plural else "one"]
    return f"{term}s" if plural else term


# --- Notification control ------------------------------------------------

def notification_rule_for(tenant, event: str, audience: str = "guardians"):
    return NotificationRule.objects.filter(
        tenant=tenant, event=event, audience=audience, is_active=True,
    ).first()


def notification_channels(tenant, event: str, audience: str = "guardians") -> dict:
    rule = notification_rule_for(tenant, event, audience)
    if not rule:
        return {"sms": False, "email": False, "push": False, "in_app": False}
    return {
        "sms": rule.send_sms, "email": rule.send_email,
        "push": rule.send_push, "in_app": rule.send_in_app,
    }
