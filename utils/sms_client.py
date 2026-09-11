import json
import re
import africastalking
import logging
from decouple import config
from typing import List, TypedDict, Union, Optional, Dict
from utils.validators import normalize_phone_number

logger = logging.getLogger(__name__)

_sms_service = None


def _get_sms_service():
    global _sms_service
    if _sms_service is None:
        username = config("AFRICASTALKING_USERNAME").strip()
        api_key = config("AFRICASTALKING_API_KEY").strip()
        africastalking.initialize(username, api_key)
        _sms_service = africastalking.SMS
    return _sms_service

class SMSRecipientData(TypedDict):
    status: str
    number: str
    cost: float
    messageId: str


class SMSResponseData(TypedDict):
    Message: str
    Recipients: List[SMSRecipientData]


class SMSClient:
    @staticmethod
    def _extract_error_from_payload(payload: Optional[Dict]) -> str:
        if not payload:
            return "Provider returned an empty response"

        sms_data = payload.get("SMSMessageData", {}) if isinstance(payload, dict) else {}
        recipients_data = sms_data.get("Recipients", []) or []
        if recipients_data:
            first = recipients_data[0] or {}
            status = str(first.get("status") or "").strip()
            code = str(first.get("statusCode") or "").strip()
            message = str(sms_data.get("Message") or "").strip()
            parts = [part for part in [status, f"(code {code})" if code else "", message] if part]
            if parts:
                return " ".join(parts)

        top_message = str(sms_data.get("Message") or payload.get("Message") or "").strip()
        return top_message or "Provider rejected the SMS request"

    @staticmethod
    def send_sms_detailed(
        recipients: Union[str, List[str]],
        message: str,
        sender_id: Optional[str] = None,
        enqueue: bool = False,
    ) -> Dict[str, Optional[object]]:
        if not message or not message.strip():
            logger.error("Message cannot be empty")
            return {"success": False, "response": None, "error": "Message cannot be empty"}

        if isinstance(recipients, str):
            recipients = [recipients]

        if not recipients:
            logger.error("No recipients provided")
            return {"success": False, "response": None, "error": "No recipients provided"}

        normalized_recipients = []
        invalid_recipients = []
        for phone in recipients:
            normalized = SMSClient._normalize_phone_number(phone)
            if normalized:
                normalized_recipients.append(normalized)
            else:
                invalid_recipients.append(phone)
                logger.warning(f"Skipping invalid phone number: {phone}")

        if not normalized_recipients:
            logger.error("No valid recipients after normalization")
            invalid_text = ", ".join(invalid_recipients) if invalid_recipients else "unknown"
            return {
                "success": False,
                "response": None,
                "error": f"No valid recipients after normalization: {invalid_text}",
            }

        try:
            result = SMSClient._send_with_provider(
                recipients=normalized_recipients,
                message=message,
                sender_id=sender_id,
                enqueue=enqueue,
            )
            if result and SMSClient._payload_is_success(result):
                return {"success": True, "response": result, "error": None}
            first_error = SMSClient._extract_error_from_payload(result)
        except Exception as e:
            logger.error(
                f"Error while sending SMS to {normalized_recipients}: {e}",
                exc_info=True,
            )
            first_error = str(e)

        if sender_id:
            logger.warning(
                "Retrying SMS to %s without sender_id after initial failure.",
                normalized_recipients,
            )
            try:
                result = SMSClient._send_with_provider(
                    recipients=normalized_recipients,
                    message=message,
                    sender_id=None,
                    enqueue=enqueue,
                )
                if result and SMSClient._payload_is_success(result):
                    return {"success": True, "response": result, "error": None}
                return {
                    "success": False,
                    "response": result,
                    "error": SMSClient._extract_error_from_payload(result),
                }
            except Exception as e:
                logger.error(
                    "Retry without sender_id failed for %s: %s",
                    normalized_recipients,
                    e,
                    exc_info=True,
                )
                return {"success": False, "response": None, "error": str(e)}

        return {"success": False, "response": None, "error": first_error}

    @staticmethod
    def _coerce_response_payload(response) -> Optional[Dict]:
        if isinstance(response, dict):
            return response
        if isinstance(response, str):
            try:
                payload = json.loads(response)
            except json.JSONDecodeError:
                logger.error("Unexpected SMS response payload: %s", response)
                return None
            if isinstance(payload, dict):
                return payload
        logger.error("Unsupported SMS response type: %s", type(response).__name__)
        return None

    @staticmethod
    def _payload_is_success(payload: Optional[Dict]) -> bool:
        if not payload:
            return False
        recipients_data = payload.get("SMSMessageData", {}).get("Recipients", [])
        return bool(recipients_data) and all(
            str(r.get("status", "")).lower() == "success" for r in recipients_data
        )

    @staticmethod
    def _send_with_provider(
        recipients: List[str],
        message: str,
        sender_id: Optional[str],
        enqueue: bool,
    ) -> Optional[Dict]:
        response = _get_sms_service().send(
            message=message,
            recipients=recipients,
            sender_id=sender_id,
            enqueue=enqueue,
        )
        payload = SMSClient._coerce_response_payload(response)
        if not payload:
            return None

        if SMSClient._payload_is_success(payload):
            logger.info("SMS sent successfully to %s: %s", recipients, payload)
        else:
            logger.error("Failed to send SMS to %s: %s", recipients, payload)
        return payload

    @staticmethod
    def _normalize_phone_number(phone: str) -> Optional[str]:
        normalized = normalize_phone_number(phone)
        if normalized:
            logger.debug(f"Normalized {phone} to {normalized}")
            return normalized

        logger.error(f"Invalid phone number format: {phone}")
        return None

    @staticmethod
    def send_sms(
        recipients: Union[str, List[str]],
        message: str,
        sender_id: Optional[str] = None,
        enqueue: bool = False,
    ) -> Optional[SMSResponseData]:
        result = SMSClient.send_sms_detailed(
            recipients=recipients,
            message=message,
            sender_id=sender_id,
            enqueue=enqueue,
        )
        return result["response"] if result["success"] else None