"""Persistence for connection profiles."""

from __future__ import annotations

import json
from pathlib import Path

from sqlbot_desktop.models.entities import ConnectionProfile


class ProfileRepository:
    """Load connection profiles from a local JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/connections.json")

    def load_profiles(self) -> list[ConnectionProfile]:
        if not self.path.exists():
            return self._default_profiles()

        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return self._default_profiles()

        profiles: list[ConnectionProfile] = []
        for item in payload.get("connections", []):
            profiles.append(
                ConnectionProfile(
                    name=str(item.get("name", "")),
                    driver=self._normalize_driver(str(item.get("driver", "MYSQL"))),
                    database=str(item.get("database", "")),
                    host=str(item.get("host", "")),
                    port=item.get("port"),
                    username=str(item.get("username", "")),
                    description=str(item.get("description", "")),
                    extra=str(item.get("extra", "")),
                )
            )

        return [profile for profile in profiles if profile.name]

    def save_profiles(self, profiles: list[ConnectionProfile]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "connections": [profile.to_dict() for profile in profiles],
            "security_note": "Passwords are not stored here. Users enter credentials at login/test time.",
        }
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

    def _default_profiles(self) -> list[ConnectionProfile]:
        return []

    def _normalize_driver(self, driver: str) -> str:
        aliases = {
            "QMYSQL": "MYSQL",
            "QPSQL": "POSTGRESQL",
            "MYSQL": "MYSQL",
            "POSTGRESQL": "POSTGRESQL",
        }
        return aliases.get(driver, driver)
