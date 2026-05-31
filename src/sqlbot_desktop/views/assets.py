"""Shared UI asset paths."""

from __future__ import annotations

from pathlib import Path

from sqlbot_desktop.views.theme import project_root


def asset_path(*parts: str) -> Path:
    return project_root() / "resources" / "ui" / Path(*parts)
