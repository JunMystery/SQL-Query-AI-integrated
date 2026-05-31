"""Post-build database driver fixes for PyInstaller output."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys


def dist_internal(dist_dir: Path) -> Path:
    internal = dist_dir / "_internal"
    return internal if internal.exists() else dist_dir


def copy_file(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"copied {source} -> {target}")
    return True


def copy_libpq_alias(internal_dir: Path) -> None:
    candidates = list((internal_dir / "psycopg_binary.libs").glob("libpq*.dll"))
    candidates += list(internal_dir.glob("libpq*.dll"))
    if not candidates:
        print("warning: libpq DLL not found; PostgreSQL may not load in the packaged app.")
        return
    copy_file(candidates[0], internal_dir / "LIBPQ.dll")


def main() -> int:
    dist_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/SQLBot")
    internal_dir = dist_internal(dist_dir)
    if not internal_dir.exists():
        print(f"error: build output not found: {dist_dir}")
        return 1
    copy_libpq_alias(internal_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
