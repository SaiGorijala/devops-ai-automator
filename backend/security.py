from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from .config import settings


SENSITIVE_KEYS = {
    "github_token",
    "token",
    "pem_file_content",
    "dockerhub_pass",
    "password",
    "pass",
    "secret",
}


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class SecretBox:
    def __init__(self) -> None:
        raw_key = settings.encryption_key
        if raw_key:
            key = raw_key.encode("utf-8")
        else:
            key = _derive_key(settings.app_secret_key)
        try:
            self._fernet = Fernet(key)
        except ValueError:
            self._fernet = Fernet(_derive_key(raw_key or settings.app_secret_key))

    def encrypt_json(self, data: dict[str, Any]) -> dict[str, str]:
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return {"encrypted": self._fernet.encrypt(payload).decode("utf-8")}

    def decrypt_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        encrypted = payload.get("encrypted")
        if not encrypted:
            return payload
        raw = self._fernet.decrypt(encrypted.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("***" if key.lower() in SENSITIVE_KEYS else redact(inner))
            for key, inner in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


secret_box = SecretBox()
