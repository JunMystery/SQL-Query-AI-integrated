"""Service tests for the local GGUF sidecar integration."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig  # noqa: E402
from sqlbot_desktop.services.ai_engine import AIEngine  # noqa: E402
from sqlbot_desktop.services.llm_sidecar import LlmSidecar  # noqa: E402


class LlmSidecarTests(unittest.TestCase):
    def test_find_free_port(self) -> None:
        port = LlmSidecar()._find_free_port()

        self.assertIsInstance(port, int)
        self.assertGreater(port, 0)

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

    def test_start_sidecar_health_when_published(self) -> None:
        sidecar = LlmSidecar()
        executable = sidecar._sidecar_executable()
        if not executable.exists():
            self.skipTest(f"LLM host is not published: {executable}")

        try:
            response = sidecar.ensure_running()
            self.assertTrue(response.ok, response.message)
            self.assertTrue(sidecar.health().ok)
        finally:
            sidecar.stop()


if __name__ == "__main__":
    unittest.main()
