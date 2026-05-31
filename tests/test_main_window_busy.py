"""Smoke tests for MainWindow busy controls."""

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
from sqlbot_desktop.views.main_window import MainWindow  # noqa: E402


class MainWindowBusyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_busy_state_replaces_send_button_with_stop_button(self) -> None:
        window = MainWindow()

        self.assertTrue(window.send_button.isVisibleTo(window))
        self.assertFalse(window.stop_button.isVisibleTo(window))

        window.set_busy(True, "AI đang suy nghĩ...", "Đang xử lý yêu cầu.")

        self.assertFalse(window.send_button.isVisibleTo(window))
        self.assertTrue(window.stop_button.isVisibleTo(window))

        window.set_busy(False)

        self.assertTrue(window.send_button.isVisibleTo(window))
        self.assertFalse(window.stop_button.isVisibleTo(window))

    def test_send_action_cancels_when_busy(self) -> None:
        window = MainWindow()
        events: list[str] = []
        window.generate_requested.connect(lambda text: events.append(f"generate:{text}"))
        window.cancel_requested.connect(lambda: events.append("cancel"))

        window.question_input.setPlainText("Liệt kê khách hàng")
        window.set_busy(True, "AI đang suy nghĩ...", "")
        window._on_send_clicked()

        self.assertEqual(events, ["cancel"])

    def test_ai_model_config_preserves_self_correction_retries(self) -> None:
        window = MainWindow()

        window.set_ai_model_config(AIModelConfig(backend=AIBackend.API, self_correction_retries=5))

        self.assertEqual(window.ai_model_config().self_correction_retries, 5)


if __name__ == "__main__":
    unittest.main()
