"""Tests for login window profile state."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication

from sqlbot_desktop.models.entities import ConnectionProfile
from sqlbot_desktop.views.login_window import LoginWindow


class LoginWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_set_profiles_restores_remembered_username(self) -> None:
        window = LoginWindow()

        window.set_profiles([
            ConnectionProfile(
                name="Demo",
                driver="MYSQL",
                database="demo",
                username="report_user",
            )
        ])

        self.assertEqual(window.username_input.text(), "report_user")
        self.assertTrue(window.remember_user_checkbox.isChecked())

    def test_set_profiles_clears_username_when_profile_has_no_saved_user(self) -> None:
        window = LoginWindow()
        window.username_input.setText("old_user")
        window.remember_user_checkbox.setChecked(True)

        window.set_profiles([
            ConnectionProfile(
                name="Demo",
                driver="MYSQL",
                database="demo",
            )
        ])

        self.assertEqual(window.username_input.text(), "")
        self.assertFalse(window.remember_user_checkbox.isChecked())


if __name__ == "__main__":
    unittest.main()
