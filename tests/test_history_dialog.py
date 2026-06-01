"""Tests for history dialog rendering."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication

from sqlbot_desktop.infrastructure.activity_repository import ActivityRepository
from sqlbot_desktop.views.dialogs.history_dialog import HistoryDialog


class HistoryDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_history_dialog_renders_action_widgets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = ActivityRepository(Path(tmpdir) / "activity.sqlite")
            repository.add_history("List users", "SELECT * FROM users", True)

            dialog = HistoryDialog(repository)

            self.assertEqual(dialog.table.rowCount(), 1)
            self.assertEqual(dialog.table.columnCount(), 5)
            self.assertIsNone(dialog.table.cellWidget(0, 0))
            self.assertFalse(dialog.insert_button.isHidden())
            self.assertFalse(dialog.bookmark_button.isHidden())


if __name__ == "__main__":
    unittest.main()
