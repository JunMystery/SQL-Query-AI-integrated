"""AI backend orchestration for text-to-SQL using in-process llama-cpp-python."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

import threading

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, GenerationResult
from sqlbot_desktop.services.prompt_builder import PromptBuilder
from sqlbot_desktop.services.query_validator import QueryValidator


class AIEngine:
    """Load/unload local models and generate SQL via local or API backends."""

    API_KEY_ENV = "SQLBOT_AI_API_KEY"

    def __init__(self) -> None:
        self.config: AIModelConfig | None = None
        self.model = None  # Holds the llama_cpp.Llama object when loaded
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        if self.config is None:
            return False
        if self.config.backend == AIBackend.LOCAL:
            return self.model is not None
        return bool(self.config.api_endpoint and self.config.api_model)

    def load(self, config: AIModelConfig, check_cancelled: Callable[[], bool] | None = None) -> GenerationResult:
        self.unload()
        if check_cancelled and check_cancelled():
            return GenerationResult(False, message="Thao tác bị hủy")
        if config.backend == AIBackend.LOCAL:
            return self._load_local(config, check_cancelled)
        return self._load_api(config)

    def unload(self) -> None:
        self.model = None
        self.config = None

    def generate(
        self,
        question: str,
        schema_context: str = "",
        dialect: str = "",
        check_cancelled: Callable[[], bool] | None = None,
    ) -> GenerationResult:
        if not self.is_loaded or self.config is None:
            return GenerationResult(False, message="Chưa load AI backend.")
        if len(question.strip()) < 3:
            return GenerationResult(False, message="Câu hỏi quá ngắn.")

        prompt = PromptBuilder.build(question.strip(), schema_context, dialect)
        try:
            if self.config.backend == AIBackend.LOCAL:
                raw_text = self._generate_local(prompt, check_cancelled)
            else:
                raw_text = self._generate_api(prompt, check_cancelled)
        except Exception as exc:
            if str(exc) in ("Cancelled", "Thao tác bị hủy"):
                return GenerationResult(False, message="Thao tác bị hủy")
            return GenerationResult(False, message=str(exc))

        queries = self._extract_queries(raw_text)
        safe_queries = QueryValidator.filter_readonly(queries)
        if not safe_queries:
            return GenerationResult(False, message="AI không trả về câu SELECT hợp lệ.")
        return GenerationResult(True, queries=safe_queries[:3], message="Đã sinh SQL.")

    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        check_cancelled: Callable[[], bool] | None = None,
    ) -> str:
        """Generate response for a multi-turn chat assistant conversation."""
        if not self.is_loaded or self.config is None:
            raise RuntimeError("Chưa load AI backend.")

        try:
            if self.config.backend == AIBackend.LOCAL:
                if self.model is None:
                    raise RuntimeError("Model chưa được load.")
                # Local GGUF uses messages format directly with create_chat_completion
                with self._lock:
                    response = self.model.create_chat_completion(
                        messages=messages,
                        max_tokens=self.config.max_tokens or 512,
                        temperature=0.7,  # slightly higher temperature for assistant conversation
                        stream=True,
                    )
                    collected_text = ""
                    for chunk in response:
                        if check_cancelled and check_cancelled():
                            raise RuntimeError("Cancelled")
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            if "content" in delta:
                                collected_text += delta["content"]
                    return collected_text
            else:
                # API AI backend
                payload = {
                    "model": self.config.api_model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": self.config.max_tokens or 512,
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
                        if check_cancelled and check_cancelled():
                            raise RuntimeError("Cancelled")
                        payload = json.loads(response.read().decode("utf-8"))
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                    raise RuntimeError(f"Gọi API thất bại: {exc}") from exc

                choices = payload.get("choices", [])
                if not choices:
                    return ""
                message = choices[0].get("message", {})
                return str(message.get("content", ""))
        except Exception as exc:
            if str(exc) in ("Cancelled", "Thao tác bị hủy", "cancelled", "CancelledError"):
                raise RuntimeError("Cancelled") from exc
            raise exc

    def _load_local(self, config: AIModelConfig, check_cancelled: Callable[[], bool] | None = None) -> GenerationResult:
        model_path = Path(config.local_model_path)
        if model_path.suffix.lower() != ".gguf":
            return GenerationResult(False, message="Vui lòng chọn file model định dạng .gguf.")
        if not model_path.exists():
            return GenerationResult(False, message="File model không tồn tại.")

        if check_cancelled and check_cancelled():
            return GenerationResult(False, message="Thao tác bị hủy")

        try:
            from llama_cpp import Llama

            # Initialize llama model directly in the Python process
            self.model = Llama(
                model_path=str(model_path),
                n_ctx=config.context_size or 4096,
                n_threads=config.threads or 4,
                verbose=False,
            )
            self.config = config
            return GenerationResult(True, message=f"Đã load local model: {model_path.name}")
        except Exception as exc:
            self.model = None
            return GenerationResult(False, message=f"Load model thất bại: {exc}")

    def _load_api(self, config: AIModelConfig) -> GenerationResult:
        if not config.api_endpoint.strip():
            return GenerationResult(False, message="Vui lòng nhập API endpoint.")
        if not config.api_model.strip():
            return GenerationResult(False, message="Vui lòng nhập API model.")
        if not os.environ.get(self.API_KEY_ENV):
            return GenerationResult(False, message=f"Chưa cấu hình biến môi trường {self.API_KEY_ENV}.")
        self.config = config
        return GenerationResult(True, message=f"Đã chọn API model: {config.api_model}")

    def _generate_local(self, prompt: str, check_cancelled: Callable[[], bool] | None = None) -> str:
        if self.model is None:
            raise RuntimeError("Model chưa được load.")

        # Run token streaming using chat completion to apply the model's native chat template
        with self._lock:
            response = self.model.create_chat_completion(
                messages=[
                    {"role": "system", "content": PromptBuilder.system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.config.max_tokens or 512,
                temperature=0.1,
                stop=["</s>", "<|im_end|>", "\n\n", "Q:", "CÂU HỎI:"],
                stream=True,
            )

            collected_text = ""
            for chunk in response:
                if check_cancelled and check_cancelled():
                    raise RuntimeError("Cancelled")
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    if "content" in delta:
                        collected_text += delta["content"]

            return collected_text

    def _generate_api(self, prompt: str, check_cancelled: Callable[[], bool] | None = None) -> str:
        assert self.config is not None
        if check_cancelled and check_cancelled():
            raise RuntimeError("Cancelled")

        payload = {
            "model": self.config.api_model,
            "messages": [
                {"role": "system", "content": PromptBuilder.system_prompt()},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": self.config.max_tokens or 512,
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
                if check_cancelled and check_cancelled():
                    raise RuntimeError("Cancelled")
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
