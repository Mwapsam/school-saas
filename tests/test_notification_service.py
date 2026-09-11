"""NotificationService.dispatch — channel fan-out gated by NotificationRule."""
import uuid
from unittest.mock import patch

import pytest
from django.core import mail

from core.models import Guardian, Notification, NotificationRecipient, NotificationRule
from core.services.notification_service import NotificationService


def _guardian(school):
    return Guardian.objects.create(
        tenant=school, first_name="Gina", last_name="Guardian",
        email=f"g_{uuid.uuid4().hex[:6]}@example.com", mobile_phone="0970000000",
        is_active=True,
    )


def _recipients(*guardians):
    return [
        {"id": g.id, "type": "guardian", "phone": g.mobile_phone, "email": g.email}
        for g in guardians
    ]


@pytest.mark.django_db
class TestNotificationDispatch:
    def test_no_rule_sends_nothing(self, school):
        g = _guardian(school)
        out = NotificationService(school).dispatch(
            "announcement", "guardians", _recipients(g),
            title="Hi", message="Body",
        )
        assert out == {"in_app": 0, "sms": 0, "email": 0, "push": 0}
        assert Notification.objects.filter(tenant=school).count() == 0

    def test_in_app_only(self, school):
        NotificationRule.objects.create(
            tenant=school, event="announcement", audience="guardians",
            send_in_app=True, send_sms=False, send_email=False, send_push=False,
            is_active=True,
        )
        g1, g2 = _guardian(school), _guardian(school)
        out = NotificationService(school).dispatch(
            "announcement", "guardians", _recipients(g1, g2),
            title="Sports day", message="Saturday 9am",
        )
        assert out["in_app"] == 2
        note = Notification.objects.get(tenant=school, title="Sports day")
        assert NotificationRecipient.objects.filter(notification=note).count() == 2
        assert not mail.outbox

    def test_email_channel_uses_outbox(self, school):
        NotificationRule.objects.create(
            tenant=school, event="fee_due", audience="guardians",
            send_email=True, is_active=True,
        )
        g = _guardian(school)
        out = NotificationService(school).dispatch(
            "fee_due", "guardians", _recipients(g),
            title="Fee overdue", message="Please pay",
        )
        assert out["email"] == 1
        assert len(mail.outbox) == 1
        assert g.email in mail.outbox[0].to

    def test_sms_channel_calls_communication_service(self, school):
        NotificationRule.objects.create(
            tenant=school, event="fee_due", audience="guardians",
            send_sms=True, is_active=True,
        )
        g = _guardian(school)
        with patch("core.services.communication_service.CommunicationService.send_sms") as send:
            out = NotificationService(school).dispatch(
                "fee_due", "guardians", _recipients(g),
                title="Fee overdue", message="Pay now", sms_message="Pay now",
            )
        assert out["sms"] == 1
        send.assert_called_once()

    def test_inactive_rule_is_ignored(self, school):
        NotificationRule.objects.create(
            tenant=school, event="announcement", audience="guardians",
            send_in_app=True, is_active=False,
        )
        g = _guardian(school)
        out = NotificationService(school).dispatch(
            "announcement", "guardians", _recipients(g), title="x", message="y",
        )
        assert out["in_app"] == 0
