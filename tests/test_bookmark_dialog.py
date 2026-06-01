"""Tests for bookmark dialog editing."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication, QDialog

from sqlbot_desktop.infrastructure.activity_repository import ActivityRepository
from sqlbot_desktop.views.dialogs.bookmark_dialog import AddBookmarkDialog, BookmarksDialog


class BookmarkDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_add_bookmark_dialog_can_edit_existing_values(self) -> None:
        dialog = AddBookmarkDialog(
            "SELECT * FROM users",
            default_name="Users",
            default_category="demo",
            default_notes="note",
            editable_sql=True,
        )

        self.assertEqual(dialog.bookmark_name, "Users")
        self.assertEqual(dialog.bookmark_sql, "SELECT * FROM users")
        self.assertEqual(dialog.category, "demo")
        self.assertEqual(dialog.notes, "note")
        self.assertFalse(dialog.sql_display.isReadOnly())

    def test_bookmarks_dialog_updates_selected_bookmark(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = ActivityRepository(Path(tmpdir) / "activity.sqlite")
            repository.add_bookmark("Old", "SELECT 1", "demo", "note")
            dialog = BookmarksDialog(repository)
            entry = dialog.entries[0]

            def accept_with_changes(edit_dialog: AddBookmarkDialog) -> int:
                edit_dialog.name_input.setText("New")
                edit_dialog.sql_display.setPlainText("SELECT 2")
                edit_dialog.category_input.setText("ops")
                edit_dialog.notes_input.setPlainText("changed")
                return QDialog.DialogCode.Accepted

            with patch.object(AddBookmarkDialog, "exec", accept_with_changes):
                dialog._edit_entry(entry)

            updated = repository.list_bookmarks()[0]
            self.assertEqual(updated.question, "New")
            self.assertEqual(updated.sql, "SELECT 2")
            self.assertEqual(updated.category, "ops")
            self.assertEqual(updated.notes, "changed")


if __name__ == "__main__":
    unittest.main()
