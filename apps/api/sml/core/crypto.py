"""AES-256-GCM field encryption for secrets at rest (TOTP handled by allauth; used for billing keys)."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.db import models

_PREFIX = "enc:v1:"


def _key() -> bytes:
    raw = settings.FIELD_ENCRYPTION_KEY
    if not raw:
        raise RuntimeError("FIELD_ENCRYPTION_KEY is not configured")
    # Derive a fixed 32-byte key from whatever the operator supplied.
    return hashlib.sha256(raw.encode()).digest()


def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return _PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt(token: str) -> str:
    if not token.startswith(_PREFIX):
        raise ValueError("Not an encrypted value")
    blob = base64.urlsafe_b64decode(token[len(_PREFIX):])
    return AESGCM(_key()).decrypt(blob[:12], blob[12:], None).decode()


class EncryptedTextField(models.TextField):
    """Stores AES-GCM ciphertext; exposes plaintext on the model instance."""

    def from_db_value(self, value, expression, connection):  # type: ignore[no-untyped-def]
        if value in (None, ""):
            return value
        return decrypt(value)

    def get_prep_value(self, value):  # type: ignore[no-untyped-def]
        if value in (None, ""):
            return value
        return encrypt(str(value))
