"""Runtime setup for source and frozen builds."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QCoreApplication


def configure_qt_plugin_paths() -> None:
    """Add bundled Qt plugin paths when running from a PyInstaller build."""

    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        executable_root = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                bundle_root / "PySide6" / "plugins",
                bundle_root / "plugins",
                executable_root / "_internal" / "PySide6" / "plugins",
                executable_root / "_internal" / "plugins",
                executable_root / "PySide6" / "plugins",
                executable_root / "plugins",
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            QCoreApplication.addLibraryPath(str(candidate))
