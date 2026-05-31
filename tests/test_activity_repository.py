"""Tests for local history and bookmark persistence."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.infrastructure.activity_repository import ActivityRepository  # noqa: E402


class ActivityRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path(tempfile.gettempdir()) / "sqlbot_activity_unit.sqlite"
        self.db_path.unlink(missing_ok=True)
        self.repository = ActivityRepository(self.db_path)

    def tearDown(self) -> None:
        self.db_path.unlink(missing_ok=True)

    def test_history_keeps_latest_100_items(self) -> None:
        for index in range(105):
            self.repository.add_history(f"question {index}", f"select {index};", True)

        entries = self.repository.list_history()

        self.assertEqual(len(entries), 100)
        self.assertEqual(entries[0].question, "question 104")

    def test_bookmarks_can_be_added_and_deleted(self) -> None:
        self.repository.add_bookmark("question", "select 1;", "demo", "note")

        entries = self.repository.list_bookmarks()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].category, "demo")

        self.repository.delete_bookmark(entries[0].id)

        self.assertEqual(self.repository.list_bookmarks(), [])


if __name__ == "__main__":
    unittest.main()
