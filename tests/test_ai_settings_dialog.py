"""Smoke tests for AI settings labels that affect local GGUF resource usage."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig  # noqa: E402
from sqlbot_desktop.views.dialogs.ai_settings_dialog import AISettingsDialog  # noqa: E402


class AISettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_threads_setting_explains_worker_threads_not_cpu_cap(self) -> None:
        dialog = AISettingsDialog(AIModelConfig(backend=AIBackend.LOCAL, threads=4))

        self.assertEqual(dialog.threads_label.text(), "Luồng suy luận LLM")
        self.assertIn("worker thread llama.cpp", dialog.threads_spin.toolTip())
        self.assertIn("không phải giới hạn % CPU", dialog.threads_hint.text())
        self.assertIn("Luồng suy luận LLM: 4", dialog.resource_info.text())

    def test_defaults_match_cpu_only_laptop_profile(self) -> None:
        dialog = AISettingsDialog(AIModelConfig(backend=AIBackend.LOCAL))
        config = dialog.config()

        self.assertEqual(config.context_size, 2048)
        self.assertEqual(config.threads, 2)
        self.assertEqual(config.gpu_layers, 0)
        self.assertEqual(config.cpu_thread_limit, 4)
        self.assertEqual(config.self_correction_retries, 3)
        self.assertIn("Giới hạn app: 4", dialog.resource_info.text())


    def test_self_correction_retries_round_trip(self) -> None:
        dialog = AISettingsDialog(AIModelConfig(backend=AIBackend.API, self_correction_retries=5))

        self.assertEqual(dialog.self_correction_spin.value(), 5)
        self.assertEqual(dialog.config().self_correction_retries, 5)


if __name__ == "__main__":
    unittest.main()
