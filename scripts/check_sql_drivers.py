"""Print installed direct database drivers."""

from __future__ import annotations

import importlib.util

PYTHON_DRIVERS = {
    "SQLAlchemy": "sqlalchemy",
    "MySQL/MariaDB": "pymysql",
    "PostgreSQL": "psycopg",
}


def installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def main() -> int:
    print("Direct Python database drivers:")
    for label, module_name in PYTHON_DRIVERS.items():
        state = "installed" if installed(module_name) else "missing"
        print(f"  {label}: {state}")
    print()
    print("The app connects to MySQL and PostgreSQL through SQLAlchemy + bundled Python drivers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
