"""Verify that the packaged app contains the C# LLamaSharp sidecar."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    app_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist/SQLBot")
    host_exe = app_root / "_internal" / "runtime" / "llm_host" / "SQLBot.LlmHost.exe"

    if not host_exe.exists():
        print(f"missing LLM host: {host_exe}")
        return 1

    print(f"LLM host packaged: {host_exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
