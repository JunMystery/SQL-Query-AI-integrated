"""Application entry point for SQLBot Desktop."""

from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sqlbot_desktop.main import main


if __name__ == "__main__":
    raise SystemExit(main())
