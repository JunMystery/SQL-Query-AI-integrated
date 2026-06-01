"""Service tests for AIEngine local/API loading and cancellation behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig  # noqa: E402
from sqlbot_desktop.services.ai_engine import AIEngine  # noqa: E402


class AIEngineTests(unittest.TestCase):
    def test_rejects_non_gguf_model(self) -> None:
        result = AIEngine().load(AIModelConfig(backend=AIBackend.LOCAL, local_model_path="model.bin"))

        self.assertFalse(result.ok)
        self.assertIn(".gguf", result.message)

    def test_missing_gguf_path_has_clear_error(self) -> None:
        result = AIEngine().load(AIModelConfig(backend=AIBackend.LOCAL, local_model_path="missing.gguf"))

        self.assertFalse(result.ok)
        self.assertIn("không tồn tại", result.message.lower())

    def test_unload_multiple_times_is_safe(self) -> None:
        engine = AIEngine()

        engine.unload()
        engine.unload()

        self.assertFalse(engine.is_loaded)

    def test_cancellation_during_generation(self) -> None:
        engine = AIEngine()
        engine.config = AIModelConfig(backend=AIBackend.API, api_endpoint="http://dummy", api_model="dummy")

        result = engine.generate("Lấy danh sách tất cả nhân viên", check_cancelled=lambda: True)

        self.assertFalse(result.ok)
        self.assertIn("hủy", result.message.lower())

    def test_api_request_uses_bounded_timeout(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback) -> None:
                return None

            def read(self) -> bytes:
                return b'{"choices":[{"message":{"content":"```sql\\nSELECT 1;\\n```"}}]}'

        engine = AIEngine()
        engine.config = AIModelConfig(
            backend=AIBackend.API,
            api_endpoint="http://dummy",
            api_model="dummy",
        )

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as mocked_urlopen:
            result = engine.generate("List users")

        self.assertTrue(result.ok)
        self.assertLessEqual(mocked_urlopen.call_args.kwargs["timeout"], 60)

    def test_cancel_closes_active_api_response(self) -> None:
        class FakeResponse:
            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        engine = AIEngine()
        response = FakeResponse()
        engine._active_response = response

        engine.cancel()

        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
