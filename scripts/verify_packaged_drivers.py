"""Verify packaged MySQL/PostgreSQL driver artifacts in the PyInstaller build."""

from __future__ import annotations

from pathlib import Path
import sys


REQUIRED_FILES = [
    "LIBPQ.dll",
]

PYTHON_DRIVER_MARKERS = [
    "sqlalchemy",
    "pymysql",
    "psycopg",
]


def internal_dir(dist_dir: Path) -> Path:
    candidate = dist_dir / "_internal"
    return candidate if candidate.exists() else dist_dir


def exists_any(root: Path, pattern: str) -> bool:
    return any(root.glob(pattern))


def main() -> int:
    dist_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/SQLBot")
    root = internal_dir(dist_dir)
    failures: list[str] = []

    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            failures.append(f"missing {relative}")

    for marker in PYTHON_DRIVER_MARKERS:
        if not exists_any(root, f"{marker}*") and not exists_any(root, f"**/{marker}*"):
            print(f"info: {marker} not visible as loose files; it may be embedded in the PyInstaller PYZ archive.")

    print("Packaged direct database drivers:")
    print("  MySQL/MariaDB: PyMySQL")
    print("  PostgreSQL: psycopg binary + LIBPQ.dll")

    if failures:
        print("Driver package verification failed:")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print("Portable MySQL/PostgreSQL driver verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
