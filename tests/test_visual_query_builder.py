"""Tests for Visual Query Builder components and reactive SQL generation."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.views.components.visual_query_builder import ConditionRow, VisualQueryBuilderPanel


class VisualQueryBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_condition_row_sql_generation(self) -> None:
        columns = [
            ColumnInfo("age", "INTEGER"),
            ColumnInfo("name", "VARCHAR"),
        ]
        row = ConditionRow(columns)

        # Set integer column and numeric value
        row.col_combo.setCurrentIndex(0)
        row.op_combo.setCurrentText(">")
        row.val_input.setText("18")
        self.assertEqual(row.get_sql(), "age > 18")

        # Set string column and text value (should auto-quote)
        row.col_combo.setCurrentIndex(1)
        row.op_combo.setCurrentText("=")
        row.val_input.setText("Tú")
        self.assertEqual(row.get_sql(), "name = 'Tú'")

    def test_visual_query_builder_table_population(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT"), ColumnInfo("name", "VARCHAR")]),
            TableInfo("orders", [ColumnInfo("id", "INT"), ColumnInfo("amount", "DECIMAL")]),
        ]
        annotations = {
            "tables": {
                "users": {"description": "Người dùng"},
            }
        }
        panel.set_schema(tables, annotations)

        # Combo should display description for users, but fallback to orders name
        self.assertEqual(panel.table_combo.itemText(0), "Người dùng (users)")
        self.assertEqual(panel.table_combo.itemText(1), "orders")
