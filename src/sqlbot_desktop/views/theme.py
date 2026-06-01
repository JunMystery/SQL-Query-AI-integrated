"""Shared theme helpers supporting Light and Dark modes."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QSettings


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        executable_root = Path(sys.executable).resolve().parent
        candidates = [
            Path(getattr(sys, "_MEIPASS", executable_root)),
            executable_root / "_internal",
            executable_root,
        ]
        for candidate in candidates:
            if (candidate / "resources").exists():
                return candidate
        return executable_root
    return Path(__file__).resolve().parents[3]


def load_stylesheet(theme_name: str | None = None) -> str:
    if theme_name is None:
        settings = QSettings("SQLBot", "SQLBotDesktop")
        theme_name = settings.value("theme", "light")

    style_path = project_root() / "resources" / "ui" / "styles" / f"{theme_name}.qss"
    if not style_path.exists():
        # Fallback to light theme if dark.qss doesn't exist
        style_path = project_root() / "resources" / "ui" / "styles" / "light.qss"
    if not style_path.exists():
        return ""
    return style_path.read_text(encoding="utf-8")
