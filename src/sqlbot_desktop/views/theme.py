"""Shared theme helpers."""

from __future__ import annotations

from pathlib import Path
import sys


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


def load_stylesheet() -> str:
    style_path = project_root() / "resources" / "ui" / "styles" / "light.qss"
    if not style_path.exists():
        return ""
    return style_path.read_text(encoding="utf-8")
