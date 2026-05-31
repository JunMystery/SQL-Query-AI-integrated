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
            ColumnInfo("users.name", "VARCHAR"),
        ]
        annotations = {
            "tables": {
                "users": {
                    "columns": {
                        "name": {"description": "Tên người dùng"},
                        "age": {"description": "Tuổi tác"}
                    }
                }
            }
        }
        row = ConditionRow(columns, annotations)

        # Combo should resolve descriptions
        self.assertEqual(row.col_combo.itemText(0), "Tuổi tác (age)")
        self.assertEqual(row.col_combo.itemText(1), "Tên người dùng (users.name)")

        # Set integer column and numeric value
        row.col_combo.setCurrentIndex(0)
        row.op_combo.setCurrentText(">")
        row.val_input.setText("18")
        self.assertEqual(row.get_sql(), "age > 18")

        # Set string column and text value (should auto-quote)
        row.col_combo.setCurrentIndex(1)
        row.op_combo.setCurrentText("=")
        row.val_input.setText("Tú")
        self.assertEqual(row.get_sql(), "users.name = 'Tú'")

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

    def test_distinct_and_aggregates_sql_generation(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT"), ColumnInfo("name", "VARCHAR")]),
        ]
        panel.set_schema(tables, {})

        # Select table 'users'
        panel.table_combo.setCurrentIndex(0)
        panel._on_table_changed()

        # Find checkboxes in the column list and toggle one
        from PySide6.QtWidgets import QCheckBox
        checkboxes = panel.findChildren(QCheckBox)
        col_cbs = [cb for cb in checkboxes if cb.property("col_name") is not None]
        
        # Toggle 'id'
        id_cb = next(cb for cb in col_cbs if cb.property("col_name") == "id")
        id_cb.setChecked(True)

        # Expected query should select id
        self.assertIn("SELECT u.id", panel.sql_editor.toPlainText())

        # Now test DISTINCT
        panel.distinct_check.setChecked(True)
        self.assertIn("SELECT DISTINCT u.id", panel.sql_editor.toPlainText())

        # Now test aggregate function
        item = panel.sort_list.item(0)
        self.assertIsNotNone(item)
        
        panel._apply_column_function(item, "COUNT")
        self.assertEqual(item.text(), "COUNT(id (INT))")
        self.assertIn("SELECT DISTINCT COUNT(u.id)", panel.sql_editor.toPlainText())

        # Revert aggregate function
        panel._apply_column_function(item, None)
        self.assertEqual(item.text(), "id (INT)")
        self.assertIn("SELECT DISTINCT u.id", panel.sql_editor.toPlainText())
