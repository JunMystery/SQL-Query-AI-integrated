"""Build SQLBot Desktop as a Windows EXE with packaged SQL drivers."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, skip: bool = False) -> None:
    if skip:
        print(f"skip: {' '.join(command)}")
        return
    print(f"run: {' '.join(command)}")
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def dotnet_has_sdk() -> bool:
    result = subprocess.run(["dotnet", "--list-sdks"], cwd=PROJECT_ROOT, capture_output=True, text=True)
    return result.returncode == 0 and bool(result.stdout.strip())


def stop_running_packaged_app() -> None:
    if sys.platform != "win32":
        return

    dist_root = PROJECT_ROOT / "dist" / "SQLBot"
    if not dist_root.exists():
        return

    script = r"""
$root = [System.IO.Path]::GetFullPath($env:SQLBOT_BUILD_DIST_ROOT)
Get-CimInstance Win32_Process |
    Where-Object {
        ($_.Name -in @('SQLBot.exe', 'SQLBot.LlmHost.exe')) -and
        $_.ExecutablePath -and
        ([System.IO.Path]::GetFullPath($_.ExecutablePath).StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase))
    } |
    ForEach-Object {
        Write-Host "stopping: $($_.Name) pid=$($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force
    }
"""
    env = os.environ.copy()
    env["SQLBOT_BUILD_DIST_ROOT"] = str(dist_root)
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
    )


def publish_llm_host(skip: bool = False) -> None:
    pass


def copy_llm_host() -> None:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SQLBot Desktop EXE.")
    parser.add_argument("--skip-install", action="store_true", help="Do not install requirements before building.")
    parser.add_argument("--skip-pyinstaller", action="store_true", help="Run checks/post-build scripts without rebuilding.")
    parser.add_argument("--skip-llm-host", action="store_true", help="Do not publish/copy the C# LLamaSharp sidecar (Deprecated).")
    args = parser.parse_args()

    python = sys.executable
    if not args.skip_install:
        run([python, "-m", "pip", "install", "-r", "requirements.txt", "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu"])

    run([python, "scripts/check_sql_drivers.py"])
    if not args.skip_pyinstaller:
        stop_running_packaged_app()
    run(
        [python, "-m", "PyInstaller", "--clean", "--noconfirm", "SQLBot.spec"],
        skip=args.skip_pyinstaller,
    )
    run([python, "scripts/post_build_sql_drivers.py", "dist/SQLBot"])
    run([python, "scripts/verify_packaged_drivers.py", "dist/SQLBot"])

    print()
    print("Build complete: dist/SQLBot/SQLBot.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
