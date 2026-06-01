"""Tests for reusable dialog data-table behavior."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView, QHeaderView, QTableWidget

from sqlbot_desktop.infrastructure.activity_repository import ActivityRepository
from sqlbot_desktop.views.dialogs.bookmark_dialog import BookmarksDialog
from sqlbot_desktop.views.dialogs.history_dialog import HistoryDialog
from sqlbot_desktop.views.dialogs.query_results_dialog import QueryResultsDialog


class DataTableBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def assert_query_result_table_behavior(self, table: QTableWidget) -> None:
        self.assertEqual(table.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.assertEqual(table.horizontalScrollMode(), QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.assertEqual(table.selectionBehavior(), QAbstractItemView.SelectionBehavior.SelectRows)
        self.assertEqual(table.selectionMode(), QAbstractItemView.SelectionMode.SingleSelection)
        self.assertEqual(table.editTriggers(), QAbstractItemView.EditTrigger.NoEditTriggers)
        self.assertFalse(table.wordWrap())
        self.assertFalse(table.horizontalHeader().stretchLastSection())
        self.assertEqual(
            table.horizontalHeader().sectionResizeMode(0),
            QHeaderView.ResizeMode.Interactive,
        )

    def test_query_results_table_supports_horizontal_scroll_and_column_resize(self) -> None:
        dialog = QueryResultsDialog()
        dialog.set_results(["very_long_column_name", "value"], [["x" * 120, "1"]])

        self.assert_query_result_table_behavior(dialog.results_table)
        self.assertLessEqual(dialog.results_table.columnWidth(0), 260)

    def test_history_table_reuses_query_results_table_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = ActivityRepository(Path(tmpdir) / "activity.sqlite")
            repository.add_history("List users" * 40, "SELECT * FROM users " * 40, True)

            dialog = HistoryDialog(repository)

            self.assert_query_result_table_behavior(dialog.table)
            self.assertTrue(dialog.table.horizontalHeaderItem(0).text())
            self.assertIsNone(dialog.table.cellWidget(0, 0))
            self.assertFalse(dialog.insert_button.isHidden())
            self.assertFalse(dialog.bookmark_button.isHidden())
            self.assertTrue(dialog.insert_button.text())
            self.assertTrue(dialog.bookmark_button.text())
            self.assertLessEqual(dialog.table.columnWidth(2), 260)
            self.assertLessEqual(dialog.table.columnWidth(3), 260)

    def test_bookmarks_table_reuses_query_results_table_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = ActivityRepository(Path(tmpdir) / "activity.sqlite")
            repository.add_bookmark("List users" * 40, "SELECT * FROM users " * 40, "demo", "note" * 40)

            dialog = BookmarksDialog(repository)

            self.assert_query_result_table_behavior(dialog.table)
            self.assertTrue(dialog.table.horizontalHeaderItem(0).text())
            self.assertIsNone(dialog.table.cellWidget(0, 0))
            self.assertFalse(dialog.edit_button.isHidden())
            self.assertFalse(dialog.insert_button.isHidden())
            self.assertTrue(dialog.edit_button.text())
            self.assertTrue(dialog.insert_button.text())
            self.assertLessEqual(dialog.table.columnWidth(2), 260)
            self.assertLessEqual(dialog.table.columnWidth(3), 260)
            self.assertLessEqual(dialog.table.columnWidth(4), 260)


if __name__ == "__main__":
    unittest.main()
