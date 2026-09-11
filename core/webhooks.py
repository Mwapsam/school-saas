"""Inbound QuickBooks webhook receiver.

Intuit posts to one fixed URL for the whole (shared) app - there is no tenant
subdomain to resolve on, unlike the OAuth callback. This view therefore:

1. Verifies the ``intuit-signature`` header (HMAC-SHA256 over the raw body,
   keyed by the app's webhook Verifier Token) before trusting anything.
2. Parses ``eventNotifications[].realmId`` + changed entities.
3. Hands each changed entity to a Celery task (``process_quickbooks_webhook_event``)
   and returns 200 immediately - Intuit expects a fast response and retries
   on timeout/non-2xx, so all real work (re-fetching the entity, reconciling
   against local state) happens asynchronously.

Nothing here ever mutates the local financial ledger - see
``core.tasks.process_quickbooks_webhook_event`` for why.
"""
import base64
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

logger = logging.getLogger(__name__)


def _verify_intuit_signature(raw_body: bytes, signature_header: str) -> bool:
    verifier_token = getattr(settings, "QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN", "")
    if not verifier_token or not signature_header:
        return False
    expected = base64.b64encode(
        hmac.new(verifier_token.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature_header)


@method_decorator(csrf_exempt, name="dispatch")
class QuickBooksWebhookView(View):
    """POST /webhooks/quickbooks/ - public, unauthenticated, signature-verified."""

    def post(self, request, *args, **kwargs):
        raw_body = request.body
        signature = request.headers.get("intuit-signature", "")

        if not _verify_intuit_signature(raw_body, signature):
            logger.warning("Rejected QuickBooks webhook: invalid or missing intuit-signature")
            return HttpResponseForbidden("invalid signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            logger.warning("Rejected QuickBooks webhook: unparsable JSON body")
            return HttpResponse(status=400)

        from core.tasks import process_quickbooks_webhook_event

        for notification in payload.get("eventNotifications", []):
            realm_id = notification.get("realmId")
            entities = (notification.get("dataChangeEvent") or {}).get("entities", [])
            for entity in entities:
                name = entity.get("name")
                if name not in ("Invoice", "Payment", "Customer"):
                    continue
                process_quickbooks_webhook_event.delay(
                    realm_id=realm_id,
                    entity_name=name,
                    entity_id=entity.get("id"),
                    operation=entity.get("operation"),
                    last_updated=entity.get("lastUpdated"),
                )

        # Intuit only cares about a 200 within a few seconds; the body is ignored.
        return HttpResponse(status=200)
