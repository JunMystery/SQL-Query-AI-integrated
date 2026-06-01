"""AI backend orchestration for text-to-SQL using local GGUF or API backends."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
import threading
import urllib.error
import urllib.request

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, GenerationResult
from sqlbot_desktop.services.prompt_builder import PromptBuilder
from sqlbot_desktop.services.query_validator import QueryValidator
from sqlbot_desktop.services.sql_extractor import SQLExtractor


class AIEngine:
    """Load/unload AI backends and generate SQL."""

    API_KEY_ENV = "SQLBOT_AI_API_KEY"
    API_REQUEST_TIMEOUT_SECONDS = 60

    def __init__(self) -> None:
        self.config: AIModelConfig | None = None
        self.model = None
        self._lock = threading.Lock()
        self._response_lock = threading.Lock()
        self._active_response = None

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
        import gc

        self.cancel()
        self.model = None
        self.config = None
        gc.collect()

    def cancel(self) -> None:
        with self._response_lock:
            response = self._active_response
        if response is not None:
            try:
                response.close()
            except OSError:
                pass

    def generate(
        self,
        question: str,
        schema_context: str = "",
        dialect: str = "",
        check_cancelled: Callable[[], bool] | None = None,
    ) -> GenerationResult:
        if len(question.strip()) < 3:
            return GenerationResult(False, message="Câu hỏi quá ngắn.")
        prompt = PromptBuilder.build(question.strip(), schema_context, dialect)
        return self.generate_prompt(prompt, check_cancelled=check_cancelled)

    def generate_prompt(
        self,
        prompt: str,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> GenerationResult:
        if not self.is_loaded or self.config is None:
            return GenerationResult(False, message="Chưa load AI backend.")

        try:
            if self.config.backend == AIBackend.LOCAL:
                raw_text = self._generate_local(prompt, check_cancelled)
            else:
                raw_text = self._generate_api(prompt, check_cancelled)
        except Exception as exc:
            if str(exc) in ("Cancelled", "Thao tác bị hủy"):
                return GenerationResult(False, message="Thao tác bị hủy")
            return GenerationResult(False, message=str(exc))

        safe_queries = QueryValidator.filter_readonly(SQLExtractor.extract_select_queries(raw_text))
        if not safe_queries:
            return GenerationResult(False, message=raw_text or "AI không trả về câu SELECT hợp lệ.")
        return GenerationResult(True, queries=safe_queries[:3], message=raw_text)

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
                with self._lock:
                    response = self.model.create_chat_completion(
                        messages=messages,
                        max_tokens=self.config.max_tokens or 512,
                        temperature=0.7,
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

            payload = {
                "model": self.config.api_model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": self.config.max_tokens or 512,
            }
            response_payload = self._post_chat_payload(payload, check_cancelled)
            choices = response_payload.get("choices", [])
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

            optimal_threads = config.threads
            if not optimal_threads:
                cpu_cores = os.cpu_count()
                optimal_threads = max(1, (cpu_cores or 4) - 1)

            self.model = Llama(
                model_path=str(model_path),
                n_ctx=config.context_size or 2048,
                n_threads=optimal_threads,
                n_gpu_layers=getattr(config, "gpu_layers", 0),
                n_batch=512,
                verbose=False,
            )
            if check_cancelled and check_cancelled():
                self.model = None
                self.config = None
                return GenerationResult(False, message="Thao tác bị hủy")
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
        self.config = config
        return GenerationResult(True, message=f"Đã chọn API model: {config.api_model}")

    def _generate_local(self, prompt: str, check_cancelled: Callable[[], bool] | None = None) -> str:
        if self.model is None:
            raise RuntimeError("Model chưa được load.")

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
        response_payload = self._post_chat_payload(payload, check_cancelled)
        choices = response_payload.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return str(message.get("content", ""))

    def _post_chat_payload(
        self,
        payload: dict,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> dict:
        assert self.config is not None
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(
            self.config.api_endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            if check_cancelled and check_cancelled():
                raise RuntimeError("Cancelled")
            with urllib.request.urlopen(request, timeout=self.API_REQUEST_TIMEOUT_SECONDS) as response:
                with self._response_lock:
                    self._active_response = response
                try:
                    if check_cancelled and check_cancelled():
                        raise RuntimeError("Cancelled")
                    raw_payload = response.read()
                    if check_cancelled and check_cancelled():
                        raise RuntimeError("Cancelled")
                    return json.loads(raw_payload.decode("utf-8"))
                finally:
                    with self._response_lock:
                        if self._active_response is response:
                            self._active_response = None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            if check_cancelled and check_cancelled():
                raise RuntimeError("Cancelled") from exc
            raise RuntimeError(f"Gọi API thất bại: {exc}") from exc

    def _extract_queries(self, raw_text: str) -> list[str]:
        return SQLExtractor.extract_select_queries(raw_text)
