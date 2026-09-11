"""Single dispatch point for system notifications.

Every event that wants to notify someone calls :meth:`NotificationService.dispatch`
with an event key, an audience, and a list of recipients. The service asks
:func:`core.services.configuration_service.notification_channels` which channels
the school has enabled for that ``(event, audience)`` pair (Configuration →
Notification Control) and fans out only to those.

Channels:
  * ``in_app`` — a :class:`core.models.Notification` + one
    :class:`core.models.NotificationRecipient` per recipient.
  * ``sms``    — via :class:`core.services.communication_service.CommunicationService`.
  * ``email``  — Django ``send_mail`` (no-op if email isn't configured).
  * ``push``   — no transport wired yet; logged and skipped.

Best-effort: a channel failure is logged, never raised, so a notification can
never break the business action that triggered it.

Recipient dicts: ``{"id": uuid, "type": "guardian"|"student"|"employee"|"admin",
"phone": str|None, "email": str|None}``.
"""
from __future__ import annotations

import logging

from core.services.configuration_service import notification_channels

log = logging.getLogger("core.notifications")


class NotificationService:
    def __init__(self, tenant):
        self.tenant = tenant

    def dispatch(self, event, audience, recipients, *, title, message,
                 sms_message=None, notification_type=None):
        """Fan a single event out to the channels enabled for it. Returns the
        dict of channel → sent-count (0 for a disabled channel)."""
        channels = notification_channels(self.tenant, event, audience)
        recipients = [r for r in (recipients or []) if r]
        sent = {"in_app": 0, "sms": 0, "email": 0, "push": 0}

        if not any(channels.values()) or not recipients:
            return sent

        if channels["in_app"]:
            sent["in_app"] = self._in_app(recipients, title, message,
                                          notification_type or event)
        if channels["sms"]:
            sent["sms"] = self._sms(recipients, sms_message or message)
        if channels["email"]:
            sent["email"] = self._email(recipients, title, message)
        if channels["push"]:
            log.info("push channel enabled for %s/%s but no transport wired "
                     "(%d recipients)", event, audience, len(recipients))

        return sent

    # -- channels ----------------------------------------------------------

    def _in_app(self, recipients, title, message, notification_type):
        from core.models import Notification, NotificationRecipient
        try:
            note = Notification.objects.create(
                tenant=self.tenant, title=title, message=message,
                notification_type=notification_type[:100], is_active=True,
            )
            NotificationRecipient.objects.bulk_create([
                NotificationRecipient(
                    tenant=self.tenant, notification=note,
                    recipient_id=r["id"], recipient_type=r.get("type", "user"),
                )
                for r in recipients if r.get("id")
            ])
            return len(recipients)
        except Exception:
            log.exception("in-app notification failed")
            return 0

    def _sms(self, recipients, message):
        from core.services.communication_service import CommunicationService
        svc = CommunicationService(self.tenant)
        count = 0
        for r in recipients:
            phone = r.get("phone")
            if not phone:
                continue
            try:
                svc.send_sms(phone, message)
                count += 1
            except Exception:
                log.exception("sms notification failed for %s", r.get("id"))
        return count

    def _email(self, recipients, subject, message):
        from django.conf import settings
        from django.core.mail import send_mail
        addresses = [r["email"] for r in recipients if r.get("email")]
        if not addresses:
            return 0
        try:
            send_mail(
                subject, message,
                getattr(settings, "DEFAULT_FROM_EMAIL", None),
                addresses, fail_silently=True,
            )
            return len(addresses)
        except Exception:
            log.exception("email notification failed")
            return 0
