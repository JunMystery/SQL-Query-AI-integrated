"""Manage the C# LLamaSharp sidecar process."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


@dataclass(frozen=True)
class SidecarResponse:
    ok: bool
    message: str
    payload: dict | None = None


class LlmSidecar:
    """Start, stop, and call the bundled LLamaSharp HTTP host."""

    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.port: int | None = None
        self.base_url = ""

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def ensure_running(self) -> SidecarResponse:
        if self.is_running:
            return SidecarResponse(True, "LLM host đang chạy.")

        executable = self._sidecar_executable()
        if not executable.exists():
            return SidecarResponse(False, f"Không tìm thấy LLM host: {executable}")

        self.port = self._find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process = subprocess.Popen(
            [str(executable), self.base_url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=self._creation_flags(),
        )

        deadline = time.time() + 60
        while time.time() < deadline:
            health = self.health()
            if health.ok:
                return SidecarResponse(True, "LLM host đã sẵn sàng.")
            if self.process.poll() is not None:
                return SidecarResponse(False, "LLM host đã thoát ngay sau khi khởi động.")
            time.sleep(0.25)

        self.stop()
        return SidecarResponse(False, "LLM host khởi động quá lâu.")

    def load_model(self, model_path: str, context_size: int = 2048, gpu_layers: int = 0) -> SidecarResponse:
        running = self.ensure_running()
        if not running.ok:
            return running
        return self._post(
            "/v1/model/load",
            {"model_path": model_path, "context_size": context_size, "gpu_layers": gpu_layers},
            timeout=600,
        )

    def chat_completion(self, payload: dict) -> SidecarResponse:
        return self._post("/v1/chat/completions", payload, timeout=600)

    def unload(self) -> None:
        if self.is_running:
            try:
                self._post("/v1/model/unload", {}, timeout=10)
            except Exception:
                pass

    def stop(self) -> None:
        self.unload()
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None
        self.port = None
        self.base_url = ""

    def health(self) -> SidecarResponse:
        if not self.base_url:
            return SidecarResponse(False, "LLM host chưa chạy.")
        try:
            with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return SidecarResponse(True, "OK", payload)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return SidecarResponse(False, str(exc))

    def _post(self, path: str, payload: dict, timeout: int) -> SidecarResponse:
        if not self.base_url:
            return SidecarResponse(False, "LLM host chưa chạy.")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            return SidecarResponse(True, "OK", response_payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return SidecarResponse(False, self._error_message(body) or str(exc))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return SidecarResponse(False, self._friendly_transport_error(exc))

    def _error_message(self, body: str) -> str:
        if not body:
            return ""
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body
        for key in ("error", "detail", "title"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return body

    def _friendly_transport_error(self, exc: Exception) -> str:
        message = str(exc)
        if isinstance(exc, TimeoutError) or "timed out" in message.lower():
            return "LLM host phản hồi quá lâu. Model có thể quá nặng hoặc máy không đủ RAM/CPU."
        return message

    def _sidecar_executable(self) -> Path:
        if getattr(sys, "frozen", False):
            root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            candidates = [
                root / "runtime" / "llm_host" / "SQLBot.LlmHost.exe",
                Path(sys.executable).resolve().parent / "_internal" / "runtime" / "llm_host" / "SQLBot.LlmHost.exe",
                Path(sys.executable).resolve().parent / "runtime" / "llm_host" / "SQLBot.LlmHost.exe",
            ]
        else:
            project_root = Path(__file__).resolve().parents[3]
            candidates = [
                project_root / "dist" / "llm_host" / "SQLBot.LlmHost.exe",
                project_root / "llm_host" / "SQLBot.LlmHost" / "bin" / "Release" / "net8.0" / "win-x64" / "publish" / "SQLBot.LlmHost.exe",
            ]
        return next((candidate for candidate in candidates if candidate.exists()), candidates[0])

    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _creation_flags(self) -> int:
        if sys.platform == "win32":
            return subprocess.CREATE_NO_WINDOW
        return 0
