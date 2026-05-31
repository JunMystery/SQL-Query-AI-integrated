"""AI backend orchestration for text-to-SQL."""

from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, GenerationResult
from sqlbot_desktop.services.llm_sidecar import LlmSidecar
from sqlbot_desktop.services.prompt_builder import PromptBuilder
from sqlbot_desktop.services.query_validator import QueryValidator


class AIEngine:
    """Load/unload local models and generate SQL via local or API backends."""

    API_KEY_ENV = "SQLBOT_AI_API_KEY"

    def __init__(self) -> None:
        self.config: AIModelConfig | None = None
        self.sidecar = LlmSidecar()

    @property
    def is_loaded(self) -> bool:
        if self.config is None:
            return False
        if self.config.backend == AIBackend.LOCAL:
            return self.sidecar.is_running
        return bool(self.config.api_endpoint and self.config.api_model)

    def load(self, config: AIModelConfig) -> GenerationResult:
        self.unload()
        if config.backend == AIBackend.LOCAL:
            return self._load_local(config)
        return self._load_api(config)

    def unload(self) -> None:
        self.sidecar.stop()
        self.config = None

    def generate(self, question: str, schema_context: str = "", dialect: str = "") -> GenerationResult:
        if not self.is_loaded or self.config is None:
            return GenerationResult(False, message="Chưa load AI backend.")
        if len(question.strip()) < 3:
            return GenerationResult(False, message="Câu hỏi quá ngắn.")

        prompt = PromptBuilder.build(question.strip(), schema_context, dialect)
        try:
            if self.config.backend == AIBackend.LOCAL:
                raw_text = self._generate_local(prompt)
            else:
                raw_text = self._generate_api(prompt)
        except Exception as exc:
            return GenerationResult(False, message=str(exc))

        queries = self._extract_queries(raw_text)
        safe_queries = QueryValidator.filter_readonly(queries)
        if not safe_queries:
            return GenerationResult(False, message="AI không trả về câu SELECT hợp lệ.")
        return GenerationResult(True, queries=safe_queries[:3], message="Đã sinh SQL.")

    def _load_local(self, config: AIModelConfig) -> GenerationResult:
        model_path = Path(config.local_model_path)
        if model_path.suffix.lower() != ".gguf":
            return GenerationResult(False, message="Vui lòng chọn file model định dạng .gguf.")
        if not model_path.exists():
            return GenerationResult(False, message="File model không tồn tại.")

        response = self.sidecar.load_model(str(model_path), context_size=2048, gpu_layers=0)
        if not response.ok:
            self.sidecar.stop()
            return GenerationResult(False, message=f"Load model thất bại: {response.message}")

        self.config = config
        return GenerationResult(True, message=f"Đã load local model: {model_path.name}")

    def _load_api(self, config: AIModelConfig) -> GenerationResult:
        if not config.api_endpoint.strip():
            return GenerationResult(False, message="Vui lòng nhập API endpoint.")
        if not config.api_model.strip():
            return GenerationResult(False, message="Vui lòng nhập API model.")
        if not os.environ.get(self.API_KEY_ENV):
            return GenerationResult(False, message=f"Chưa cấu hình biến môi trường {self.API_KEY_ENV}.")
        self.config = config
        return GenerationResult(True, message=f"Đã chọn API model: {config.api_model}")

    def _generate_local(self, prompt: str) -> str:
        response = self.sidecar.chat_completion(
            {
                "model": "local-gguf",
                "messages": [
                    {"role": "system", "content": PromptBuilder.system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 512,
            }
        )
        if not response.ok or response.payload is None:
            raise RuntimeError(response.message)
        choices = response.payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return str(message.get("content", ""))

    def _generate_api(self, prompt: str) -> str:
        assert self.config is not None
        payload = {
            "model": self.config.api_model,
            "messages": [
                {"role": "system", "content": PromptBuilder.system_prompt()},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 512,
        }
        request = urllib.request.Request(
            self.config.api_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {os.environ[self.API_KEY_ENV]}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"Gọi API thất bại: {exc}") from exc

        choices = payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return str(message.get("content", ""))

    def _extract_queries(self, raw_text: str) -> list[str]:
        cleaned = raw_text.replace("```sql", "```").replace("```", "").strip()
        statements = [part.strip() for part in cleaned.split(";") if part.strip()]
        return [f"{statement};" for statement in statements]
