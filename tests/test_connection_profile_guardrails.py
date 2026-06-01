"""Tests for per-connection query guardrail settings."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from sqlbot_desktop.controllers.main_controller import MainController  # noqa: E402
from sqlbot_desktop.infrastructure.profile_repository import ProfileRepository  # noqa: E402
from sqlbot_desktop.models.entities import ConnectionProfile  # noqa: E402
from sqlbot_desktop.views.dialogs.connection_form_dialog import ConnectionFormDialog  # noqa: E402


class ConnectionProfileGuardrailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_profile_repository_round_trips_query_guardrails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ProfileRepository(Path(temp_dir) / "connections.json")
            repository.save_profiles([
                ConnectionProfile(
                    name="Demo",
                    driver="MYSQL",
                    database="demo",
                    host="127.0.0.1",
                    query_max_rows=250,
                    query_timeout_seconds=12,
                )
            ])

            loaded = repository.load_profiles()

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].query_max_rows, 250)
        self.assertEqual(loaded[0].query_timeout_seconds, 12)

    def test_connection_form_round_trips_query_guardrails(self) -> None:
        profile = ConnectionProfile(
            name="Demo",
            driver="POSTGRESQL",
            database="analytics",
            host="localhost",
            username="report_user",
            query_max_rows=300,
            query_timeout_seconds=25,
        )
        dialog = ConnectionFormDialog(database_manager=object(), profile=profile)

        self.assertEqual(dialog.query_max_rows_input.value(), 300)
        self.assertEqual(dialog.query_timeout_input.value(), 25)
        self.assertEqual(dialog.profile().query_max_rows, 300)
        self.assertEqual(dialog.profile().query_timeout_seconds, 25)

    def test_connection_form_uses_vertical_settings_tabs(self) -> None:
        dialog = ConnectionFormDialog(database_manager=object())

        self.assertEqual(dialog.nav_list.count(), 3)
        self.assertEqual(dialog.nav_list.item(0).text(), "Kết nối")
        self.assertEqual(dialog.nav_list.item(1).text(), "Giới hạn truy vấn")
        self.assertEqual(dialog.nav_list.item(2).text(), "Kiểm tra & Schema")
        self.assertEqual(dialog.stack.count(), 3)
        self.assertEqual(dialog.stack.currentIndex(), 0)
        for index in range(dialog.stack.count()):
            stack_page = dialog.stack.widget(index)
            self.assertIsInstance(stack_page, QScrollArea)
            self.assertTrue(stack_page.widgetResizable())

        dialog.select_test_tab()

        self.assertEqual(dialog.nav_list.currentRow(), 2)
        self.assertEqual(dialog.stack.currentIndex(), 2)

    def test_main_controller_uses_profile_query_guardrails(self) -> None:
        controller = MainController.__new__(MainController)
        controller.profile = ConnectionProfile(
            name="Demo",
            driver="MYSQL",
            database="demo",
            query_max_rows=125,
            query_timeout_seconds=8,
        )

        self.assertEqual(controller._query_max_rows(), 125)
        self.assertEqual(controller._query_timeout_seconds(), 8)


if __name__ == "__main__":
    unittest.main()
