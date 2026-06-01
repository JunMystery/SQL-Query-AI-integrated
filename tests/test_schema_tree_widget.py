"""Tests for the schema viewer tree component."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo  # noqa: E402
from sqlbot_desktop.views.components.schema_tree_widget import SchemaTreeWidget  # noqa: E402


class SchemaTreeWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_schema_viewer_collapses_all_nodes_by_default(self) -> None:
        tree = SchemaTreeWidget()

        tree.set_schema(
            [
                TableInfo(
                    "users",
                    [
                        ColumnInfo("id", "INTEGER"),
                        ColumnInfo("name", "TEXT"),
                    ],
                )
            ]
        )

        table_item = tree.topLevelItem(0)

        self.assertIsNotNone(table_item)
        self.assertFalse(table_item.isExpanded())


if __name__ == "__main__":
    unittest.main()
