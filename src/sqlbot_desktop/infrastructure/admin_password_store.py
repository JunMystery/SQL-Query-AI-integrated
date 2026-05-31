"""Local admin password verification and storage."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets


ADMIN_PASSWORD_ENV = "SQLBOT_ADMIN_PASSWORD"


class AdminPasswordStore:
    """Verify and update the local connection-management password."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/security/admin_password.json")

    def is_configured(self) -> bool:
        return self.path.exists() or bool(os.environ.get(ADMIN_PASSWORD_ENV))

    def verify(self, password: str) -> bool:
        if self.path.exists():
            return self._verify_stored(password)

        env_password = os.environ.get(ADMIN_PASSWORD_ENV, "")
        return bool(env_password) and hmac.compare_digest(password, env_password)

    def update(self, new_password: str) -> None:
        salt = secrets.token_bytes(16)
        digest = self._derive(new_password, salt)
        payload = {
            "algorithm": "pbkdf2_sha256",
            "iterations": 390000,
            "salt": base64.b64encode(salt).decode("ascii"),
            "hash": base64.b64encode(digest).decode("ascii"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)

    def _verify_stored(self, password: str) -> bool:
        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            salt = base64.b64decode(payload["salt"])
            expected_hash = base64.b64decode(payload["hash"])
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return False

        actual_hash = self._derive(password, salt)
        return hmac.compare_digest(actual_hash, expected_hash)

    def _derive(self, password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 390000)
