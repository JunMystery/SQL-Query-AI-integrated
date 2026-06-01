"""Tests for the dynamic theme loading and switcher functionality."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402

from sqlbot_desktop.views.theme import load_stylesheet  # noqa: E402
from sqlbot_desktop.views.main_window import MainWindow  # noqa: E402


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_load_stylesheet_defaults_and_explicit(self) -> None:
        # Load light style explicitly
        light_style = load_stylesheet("light")
        self.assertTrue(len(light_style) > 0)
        self.assertIn("loginRoot", light_style)
        self.assertIn("QDockWidget#schemaDock::close-button", light_style)
        self.assertIn("QDockWidget#schemaDock::float-button", light_style)
        self.assertIn("QToolButton#schemaDockCloseButton", light_style)
        self.assertIn("QToolButton#schemaDockFloatButton", light_style)
        self.assertNotIn("titlebar-close-icon: none", light_style)

        # Load dark style explicitly
        dark_style = load_stylesheet("dark")
        self.assertTrue(len(dark_style) > 0)
        self.assertIn("loginRoot", dark_style)
        self.assertIn("#09090b", dark_style)
        self.assertIn("QDockWidget#schemaDock::close-button", dark_style)
        self.assertIn("QDockWidget#schemaDock::float-button", dark_style)
        self.assertIn("QToolButton#schemaDockCloseButton", dark_style)
        self.assertIn("QToolButton#schemaDockFloatButton", dark_style)
        self.assertNotIn("titlebar-close-icon: none", dark_style)

    def test_main_window_theme_switching_menu(self) -> None:
        window = MainWindow()
        
        # Test default is loaded/checked
        settings = QSettings("SQLBot", "SQLBotDesktop")
        current_theme = settings.value("theme", "light")
        if current_theme == "dark":
            self.assertTrue(window.dark_action.isChecked())
            self.assertFalse(window.light_action.isChecked())
        else:
            self.assertTrue(window.light_action.isChecked())
            self.assertFalse(window.dark_action.isChecked())

        # Switch to dark theme
        window._change_theme("dark")
        self.assertEqual(settings.value("theme"), "dark")
        self.assertTrue(window.dark_action.isChecked())
        self.assertFalse(window.light_action.isChecked())

        # Switch to light theme
        window._change_theme("light")
        self.assertEqual(settings.value("theme"), "light")
        self.assertTrue(window.light_action.isChecked())
        self.assertFalse(window.dark_action.isChecked())

    def test_schema_dock_uses_custom_colored_title_buttons(self) -> None:
        window = MainWindow()

        self.assertEqual(window.schema_dock_widget.titleBarWidget().objectName(), "schemaDockTitleBar")
        self.assertEqual(window.schema_dock_float_button.objectName(), "schemaDockFloatButton")
        self.assertEqual(window.schema_dock_close_button.objectName(), "schemaDockCloseButton")
        self.assertEqual(window.schema_dock_close_button.text(), "X")
        self.assertTrue(window.schema_dock_float_button.text())


if __name__ == "__main__":
    unittest.main()
