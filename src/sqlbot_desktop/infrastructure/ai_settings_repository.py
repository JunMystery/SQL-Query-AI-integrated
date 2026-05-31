"""Persistence for AI model configurations."""

from __future__ import annotations

import json
from pathlib import Path

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig


class AISettingsRepository:
    """Load and save AI Model Configuration from/to a local JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/ai_settings.json")

    def load_config(self) -> AIModelConfig:
        if not self.path.exists():
            return self._default_config()

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            backend_str = data.get("backend", AIBackend.LOCAL.value)
            backend = AIBackend(backend_str) if backend_str in [b.value for b in AIBackend] else AIBackend.LOCAL
            return AIModelConfig(
                backend=backend,
                local_model_path=str(data.get("local_model_path", "")),
                api_endpoint=str(data.get("api_endpoint", "")),
                api_model=str(data.get("api_model", "")),
                context_size=int(data.get("context_size", 2048)),
                max_tokens=int(data.get("max_tokens", 512)),
                threads=int(data.get("threads", 2)),
                gpu_layers=int(data.get("gpu_layers", 0)),
                cpu_thread_limit=int(data.get("cpu_thread_limit", 4)),
                self_correction_retries=int(data.get("self_correction_retries", 3)),
                api_key=str(data.get("api_key", "")),
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return self._default_config()

    def save_config(self, config: AIModelConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "backend": config.backend.value,
            "local_model_path": config.local_model_path,
            "api_endpoint": config.api_endpoint,
            "api_model": config.api_model,
            "context_size": config.context_size,
            "max_tokens": config.max_tokens,
            "threads": config.threads,
            "gpu_layers": config.gpu_layers,
            "cpu_thread_limit": config.cpu_thread_limit,
            "self_correction_retries": config.self_correction_retries,
            "api_key": config.api_key,
        }
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _default_config(self) -> AIModelConfig:
        return AIModelConfig(backend=AIBackend.LOCAL)
