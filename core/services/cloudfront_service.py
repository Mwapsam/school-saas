"""
CloudFront signed-URL / signed-cookie service.

A single, reusable service that signs requests for the **private** CloudFront
distribution using a CloudFront key group (modern replacement for the legacy
"CloudFront key pair / PEM in settings" approach).

Usage
-----
    from core.services.cloudfront_service import get_cloudfront_signer

    signer = get_cloudfront_signer()
    url = signer.signed_url("media/reports/acme/report_123.pdf", expire_seconds=300)

    # Signed cookies (e.g. to grant access to a whole prefix for a session):
    cookies = signer.signed_cookies("media/reports/acme/*", expire_seconds=3600)

Key material
------------
The RSA private key for the CloudFront key group is read from, in order:
  1. ``AWS_CLOUDFRONT_PRIVATE_KEY``       — PEM contents (env var / secret)
  2. ``AWS_CLOUDFRONT_PRIVATE_KEY_FILE``  — path to a mounted .pem secret

Nothing is hard-coded; in production the key is delivered via a secret manager
or a mounted Docker/K8s secret. CloudFront mandates RSA-SHA1 for URL signing —
that is a CloudFront protocol requirement, not an application choice.
"""

import base64
import datetime
import functools
import json
from typing import Dict, Optional
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test.signals import setting_changed

from botocore.signers import CloudFrontSigner
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class CloudFrontSignerService:
    """Produces CloudFront signed URLs and signed cookies for private assets."""

    def __init__(self):
        self.key_id: Optional[str] = getattr(settings, "CLOUDFRONT_KEY_ID", None)
        self.domain: Optional[str] = getattr(settings, "AWS_PRIVATE_CLOUDFRONT_DOMAIN", None)
        self.default_expiry: int = int(getattr(settings, "CLOUDFRONT_SIGNED_URL_EXPIRY", 3600))
        self._private_key = self._load_private_key()
        self._signer = CloudFrontSigner(self.key_id, self._rsa_sign) if self.key_id else None

    # ── key loading ──────────────────────────────────────────────────────
    def _load_private_key(self):
        pem = getattr(settings, "CLOUDFRONT_PRIVATE_KEY", None)
        if pem:
            data = pem.encode("ascii") if isinstance(pem, str) else pem
            return serialization.load_pem_private_key(data, password=None)

        path = getattr(settings, "CLOUDFRONT_PRIVATE_KEY_FILE", None)
        if path:
            with open(path, "rb") as fh:
                return serialization.load_pem_private_key(fh.read(), password=None)
        return None

    def _rsa_sign(self, message: bytes) -> bytes:
        # CloudFront requires RSA-SHA1 for signed URLs/cookies.
        return self._private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())

    # ── guards ───────────────────────────────────────────────────────────
    @property
    def is_configured(self) -> bool:
        return bool(self.key_id and self.domain and self._private_key)

    def _require_config(self):
        if not self.is_configured:
            raise ImproperlyConfigured(
                "CloudFront signing is not configured. Set CLOUDFRONT_KEY_ID, "
                "AWS_PRIVATE_CLOUDFRONT_DOMAIN and CLOUDFRONT_PRIVATE_KEY(_FILE)."
            )

    def _expiry(self, expire_seconds: Optional[int]) -> datetime.datetime:
        seconds = expire_seconds or self.default_expiry
        return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)

    # ── public API ───────────────────────────────────────────────────────
    def signed_url(self, key_or_url: str, expire_seconds: Optional[int] = None) -> str:
        """Return a CloudFront signed URL.

        ``key_or_url`` may be a bare object key (``media/reports/…/x.pdf``) or a
        full ``https://<domain>/…`` URL. Expiry defaults to
        ``CLOUDFRONT_SIGNED_URL_EXPIRY``.
        """
        self._require_config()

        if key_or_url.startswith("http://") or key_or_url.startswith("https://"):
            url = key_or_url
        else:
            url = f"https://{self.domain}/{key_or_url.lstrip('/')}"

        return self._signer.generate_presigned_url(url, date_less_than=self._expiry(expire_seconds))

    def signed_cookies(self, resource: str, expire_seconds: Optional[int] = None) -> Dict[str, str]:
        """Return CloudFront signed cookies granting access to ``resource``.

        ``resource`` is typically a wildcard path, e.g.
        ``https://<domain>/media/reports/<schema>/*`` — grant once, then the
        browser sends the cookies for every object under that prefix.
        Returns a dict of cookie name -> value to set on the response.
        """
        self._require_config()

        if not (resource.startswith("http://") or resource.startswith("https://")):
            resource = f"https://{self.domain}/{resource.lstrip('/')}"

        expires = int(self._expiry(expire_seconds).timestamp())
        policy = {
            "Statement": [{
                "Resource": resource,
                "Condition": {"DateLessThan": {"AWS:EpochTime": expires}},
            }]
        }
        policy_json = json.dumps(policy, separators=(",", ":")).encode("utf-8")
        signature = self._rsa_sign(policy_json)

        def _b64(data: bytes) -> str:
            return base64.b64encode(data).decode("ascii").translate(
                str.maketrans("+=/", "-_~")  # CloudFront-safe base64
            )

        return {
            "CloudFront-Policy": _b64(policy_json),
            "CloudFront-Signature": _b64(signature),
            "CloudFront-Key-Pair-Id": self.key_id,
        }


@functools.lru_cache(maxsize=1)
def get_cloudfront_signer() -> CloudFrontSignerService:
    """Return a process-wide singleton signer (key parsed once)."""
    return CloudFrontSignerService()


_SIGNER_SETTINGS = frozenset({
    "CLOUDFRONT_KEY_ID",
    "CLOUDFRONT_PRIVATE_KEY",
    "CLOUDFRONT_PRIVATE_KEY_FILE",
    "AWS_PRIVATE_CLOUDFRONT_DOMAIN",
    "CLOUDFRONT_SIGNED_URL_EXPIRY",
})


def _reset_signer_cache(*, setting, **kwargs):
    if setting in _SIGNER_SETTINGS:
        get_cloudfront_signer.cache_clear()


setting_changed.connect(_reset_signer_cache)
