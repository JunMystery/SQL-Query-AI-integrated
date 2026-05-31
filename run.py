"""Application entry point for SQLBot Desktop."""

import os
from pathlib import Path
import sys

# Setup project source directory paths
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def load_env() -> None:
    """Parse and load local .env variables into os.environ for local debugging."""
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, sep, value = line.partition("=")
                if sep:
                    k = key.strip()
                    v = value.strip().strip("'\"")
                    if k:
                        os.environ[k] = v
    except Exception as exc:
        print(f"Warning: Failed to load .env file: {exc}", file=sys.stderr)


# Load environment variables and bootstrap application
load_env()

from sqlbot_desktop.main import main

if __name__ == "__main__":
    raise SystemExit(main())
