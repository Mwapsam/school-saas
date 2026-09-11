"""Encrypted model fields.

`EncryptedTextField` transparently encrypts its value at rest with Fernet
(AES-128-CBC + HMAC). Ciphertext is stored as text prefixed with ``enc:v1:``
so a plaintext value written before the column was encrypted is recognised and
returned as-is (this keeps the rollout migration and any un-migrated row
working). Callers see and set plain ``str`` values and never touch the crypto.

Key: ``settings.FIELD_ENCRYPTION_KEY`` when set, else ``settings.SECRET_KEY``.
Any string works - it is hashed to a 32-byte urlsafe key - but rotating it
makes existing ciphertext unreadable, so set a dedicated, stable
``FIELD_ENCRYPTION_KEY`` in every non-dev environment.
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    raw = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_str(value: str) -> str:
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def decrypt_str(value: str) -> str:
    """Decrypt a value produced by :func:`encrypt_str`.

    A value without the ``enc:v1:`` prefix is assumed to be legacy plaintext
    and returned unchanged. A prefixed value that fails to decrypt (wrong key,
    corruption) is returned unchanged with a warning rather than raising, so a
    single bad row never takes the whole model down.
    """
    if not value.startswith(_PREFIX):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        logger.warning("EncryptedTextField: could not decrypt a value; returning as-is")
        return value


class EncryptedTextField(models.TextField):
    """TextField whose DB representation is Fernet ciphertext."""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return decrypt_str(value)

    def to_python(self, value):
        if value is None:
            return None
        if isinstance(value, str) and value.startswith(_PREFIX):
            return decrypt_str(value)
        return value

    def get_prep_value(self, value):
        # Check the prefix on the raw argument first: super().get_prep_value
        # runs to_python, which would decrypt an already-encrypted value and
        # defeat this guard.
        if isinstance(value, str) and value.startswith(_PREFIX):
            return value  # already encrypted; don't double-wrap
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        return encrypt_str(value)
