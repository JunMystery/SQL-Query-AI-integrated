"""Tests for Visual Query Builder components and reactive SQL generation."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication, QMessageBox

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.services.join_safety_service import JoinSafetyResult
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

        # Test DATETIME auto-formatting
        datetime_cols = [
            ColumnInfo("created_at", "DATETIME"),
        ]
        row_dt = ConditionRow(datetime_cols)
        row_dt.col_combo.setCurrentIndex(0)
        row_dt.op_combo.setCurrentText("=")
        row_dt.val_input.setText("2026-06-01")
        self.assertEqual(row_dt.get_sql(), "created_at = '2026-06-01 00:00:00.000'")

        # Test BETWEEN formatting
        row_dt.op_combo.setCurrentText("BETWEEN")
        row_dt.val_input.setText("2026-06-01 12:00")
        row_dt.val_input_2.setText("2026-06-02")
        self.assertEqual(row_dt.get_sql(), "created_at BETWEEN '2026-06-01 12:00:00.000' AND '2026-06-02 00:00:00.000'")

    def test_filter_operator_combo_has_tooltips_for_all_operators(self) -> None:
        row = ConditionRow([ColumnInfo("age", "INTEGER")])

        for index in range(row.op_combo.count()):
            row.op_combo.setCurrentIndex(index)
            tooltip = row.op_combo.itemData(index, Qt.ItemDataRole.ToolTipRole)

            self.assertTrue(tooltip, row.op_combo.itemText(index))
            self.assertEqual(row.op_combo.toolTip(), tooltip)

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

    def test_column_picker_groups_collapse_and_search_expands_matches(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT"), ColumnInfo("name", "VARCHAR")]),
            TableInfo("orders", [ColumnInfo("id", "INT"), ColumnInfo("amount", "DECIMAL")]),
        ]
        panel.set_schema(tables, {})

        self.assertFalse(panel.column_groups["users"].body.isHidden())
        self.assertTrue(panel.column_groups["orders"].body.isHidden())

        panel.col_search_input.setText("amount")

        self.assertFalse(panel.column_groups["orders"].isHidden())
        self.assertFalse(panel.column_groups["orders"].body.isHidden())

    def test_join_safety_blocks_danger_candidate_column(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT")]),
            TableInfo("orders", [ColumnInfo("amount", "DECIMAL")]),
        ]
        panel.set_schema(tables, {})
        panel.set_join_safety_checker(
            lambda selected, candidate: JoinSafetyResult(
                False,
                "danger",
                "Không tìm thấy JOIN path theo schema/FK.",
                [],
            )
        )

        amount_row = next(
            row
            for row in panel.column_groups["orders"].iter_column_rows()
            if row.cb.property("col_name") == "amount"
        )
        amount_row.cb.setChecked(True)

        self.assertFalse(amount_row.cb.isChecked())
        self.assertFalse(amount_row.cb.isEnabled())
        self.assertEqual(panel.sort_list.count(), 0)
        self.assertIn("JOIN path", amount_row.toolTip())

    def test_join_safety_keeps_valid_candidate_column(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT")]),
            TableInfo("orders", [ColumnInfo("amount", "DECIMAL")]),
        ]
        panel.set_schema(tables, {})
        panel.set_join_safety_checker(
            lambda selected, candidate: JoinSafetyResult(
                True,
                "ok",
                "JOIN path hợp lệ trong mẫu kiểm tra.",
                [("users", "id", "orders", "user_id")],
                matched_sample_rows=10,
            )
        )

        amount_row = next(
            row
            for row in panel.column_groups["orders"].iter_column_rows()
            if row.cb.property("col_name") == "amount"
        )
        amount_row.cb.setChecked(True)

        self.assertTrue(amount_row.cb.isChecked())
        self.assertEqual(panel.sort_list.count(), 1)

    def test_column_toolbar_uses_compact_order_and_confirmed_clear(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT"), ColumnInfo("name", "VARCHAR")]),
        ]
        panel.set_schema(tables, {})

        controls_layout = panel.columns_group.layout().itemAt(0).layout()
        self.assertIs(controls_layout.itemAt(1).widget(), panel.show_selected_only_btn)
        self.assertIs(controls_layout.itemAt(2).widget(), panel.clear_selected_btn)
        self.assertIs(controls_layout.itemAt(3).widget(), panel.sort_dialog_btn)
        self.assertEqual(panel.clear_selected_btn.text(), "×")
        self.assertIn(panel.sort_dialog_btn.text(), {"Order", "Thứ tự", "順序"})
        self.assertLessEqual(panel.clear_selected_btn.width(), 34)
        self.assertLessEqual(panel.sort_dialog_btn.width(), 56)
        self.assertTrue(panel.clear_selected_btn.toolTip())
        self.assertTrue(panel.sort_dialog_btn.toolTip())

        from PySide6.QtWidgets import QCheckBox
        col_cbs = [
            cb for cb in panel.findChildren(QCheckBox)
            if cb.property("col_name") is not None
        ]
        id_cb = next(cb for cb in col_cbs if cb.property("col_name") == "id")
        name_cb = next(cb for cb in col_cbs if cb.property("col_name") == "name")
        id_cb.setChecked(True)
        name_cb.setChecked(True)

        with patch(
            "sqlbot_desktop.views.components.visual_query_builder.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            panel._clear_all_selected_columns()
        self.assertTrue(id_cb.isChecked())
        self.assertTrue(name_cb.isChecked())

        with patch(
            "sqlbot_desktop.views.components.visual_query_builder.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            panel._clear_all_selected_columns()
        self.assertFalse(id_cb.isChecked())
        self.assertFalse(name_cb.isChecked())

    def test_group_order_and_sql_cards_are_stacked_in_requested_order(self) -> None:
        panel = VisualQueryBuilderPanel()
        right_layout = panel.sql_title.parentWidget().layout()

        self.assertLess(right_layout.indexOf(panel.groupby_group), right_layout.indexOf(panel.orderby_group))
        self.assertLess(right_layout.indexOf(panel.orderby_group), right_layout.indexOf(panel.sql_title))
        self.assertLess(right_layout.indexOf(panel.sql_title), right_layout.indexOf(panel.sql_editor))
        self.assertGreater(panel.groupby_group.height(), 0)
        self.assertGreater(panel.orderby_group.height(), 0)
        self.assertGreaterEqual(panel.groupby_group.minimumHeight(), 190)
        self.assertGreaterEqual(panel.orderby_group.minimumHeight(), 190)
        self.assertEqual(right_layout.stretch(right_layout.indexOf(panel.groupby_group)), 1)
        self.assertEqual(right_layout.stretch(right_layout.indexOf(panel.orderby_group)), 1)

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

    def test_related_table_column_selection_generates_join(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo(
                "users",
                [
                    ColumnInfo("id", "INT", is_primary=True, nullable=False),
                    ColumnInfo("name", "VARCHAR"),
                ],
            ),
            TableInfo(
                "orders",
                [
                    ColumnInfo("id", "INT", is_primary=True, nullable=False),
                    ColumnInfo("user_id", "INT", is_foreign=True, nullable=True),
                    ColumnInfo("amount", "DECIMAL"),
                ],
                foreign_keys=[
                    {
                        "constrained_table": "orders",
                        "constrained_column": "user_id",
                        "referred_table": "users",
                        "referred_column": "id",
                    }
                ],
            ),
        ]
        panel.set_schema(tables, {})

        from PySide6.QtWidgets import QCheckBox
        col_cbs = [
            cb for cb in panel.findChildren(QCheckBox)
            if cb.property("col_name") is not None
        ]
        amount_cb = next(
            cb for cb in col_cbs
            if cb.property("table_name") == "orders" and cb.property("col_name") == "amount"
        )
        amount_cb.setChecked(True)

        sql = panel.sql_editor.toPlainText()
        self.assertIn("SELECT o.amount", sql)
        self.assertIn("FROM users u", sql)
        self.assertIn("LEFT JOIN orders o ON u.id = o.user_id", sql)
        self.assertNotEqual(sql.strip(), "SELECT orders.amount\nFROM users")

    def test_related_table_order_by_generates_join(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo(
                "users",
                [
                    ColumnInfo("id", "INT", is_primary=True, nullable=False),
                    ColumnInfo("name", "VARCHAR"),
                ],
            ),
            TableInfo(
                "orders",
                [
                    ColumnInfo("id", "INT", is_primary=True, nullable=False),
                    ColumnInfo("user_id", "INT", is_foreign=True, nullable=True),
                    ColumnInfo("amount", "DECIMAL"),
                ],
                foreign_keys=[
                    {
                        "constrained_table": "orders",
                        "constrained_column": "user_id",
                        "referred_table": "users",
                        "referred_column": "id",
                    }
                ],
            ),
        ]
        panel.set_schema(tables, {})

        from PySide6.QtWidgets import QCheckBox
        amount_cb = next(
            cb for cb in panel.findChildren(QCheckBox)
            if cb.property("table_name") == "orders" and cb.property("col_name") == "amount"
        )
        amount_cb.setChecked(True)
        panel._add_orderby_row()

        order_row = panel.orderby_container_layout.itemAt(0).widget()
        for index in range(order_row.col_combo.count()):
            if order_row.col_combo.itemData(index) == "orders.amount":
                order_row.col_combo.setCurrentIndex(index)
                break

        sql = panel.sql_editor.toPlainText()
        self.assertIn("FROM users u", sql)
        self.assertIn("LEFT JOIN orders o ON u.id = o.user_id", sql)
        self.assertIn("ORDER BY o.amount ASC", sql)

    def test_groupby_and_orderby_only_offer_selected_columns(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT"), ColumnInfo("name", "VARCHAR")]),
            TableInfo(
                "orders",
                [
                    ColumnInfo("id", "INT"),
                    ColumnInfo("user_id", "INT"),
                    ColumnInfo("amount", "DECIMAL"),
                ],
            ),
        ]
        panel.set_schema(tables, {})

        from PySide6.QtWidgets import QCheckBox
        col_cbs = [
            cb for cb in panel.findChildren(QCheckBox)
            if cb.property("col_name") is not None
        ]
        user_id_cb = next(
            cb for cb in col_cbs
            if cb.property("table_name") == "users" and cb.property("col_name") == "id"
        )
        amount_cb = next(
            cb for cb in col_cbs
            if cb.property("table_name") == "orders" and cb.property("col_name") == "amount"
        )
        user_id_cb.setChecked(True)
        amount_cb.setChecked(True)

        panel._add_groupby_row()
        panel._add_orderby_row()
        group_row = panel.groupby_container_layout.itemAt(0).widget()
        order_row = panel.orderby_container_layout.itemAt(0).widget()

        self.assertEqual(
            [group_row.col_combo.itemData(i) for i in range(group_row.col_combo.count())],
            ["id", "orders.amount"],
        )
        self.assertEqual(
            [order_row.col_combo.itemData(i) for i in range(order_row.col_combo.count())],
            ["id", "orders.amount"],
        )

        name_options = [
            group_row.col_combo.itemData(i)
            for i in range(group_row.col_combo.count())
        ]
        self.assertNotIn("name", name_options)
        self.assertNotIn("orders.user_id", name_options)

    def test_groupby_and_orderby_rows_removed_when_selected_column_is_unchecked(self) -> None:
        panel = VisualQueryBuilderPanel()
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT"), ColumnInfo("name", "VARCHAR")]),
        ]
        panel.set_schema(tables, {})

        from PySide6.QtWidgets import QCheckBox
        id_cb = next(
            cb for cb in panel.findChildren(QCheckBox)
            if cb.property("table_name") == "users" and cb.property("col_name") == "id"
        )
        id_cb.setChecked(True)
        panel._add_groupby_row()
        panel._add_orderby_row()

        def row_class_names(layout):
            return [
                layout.itemAt(i).widget().__class__.__name__
                for i in range(layout.count())
                if layout.itemAt(i).widget() is not None
            ]

        self.assertIn("GroupByRow", row_class_names(panel.groupby_container_layout))
        self.assertIn("OrderByRow", row_class_names(panel.orderby_container_layout))

        id_cb.setChecked(False)

        self.assertNotIn("GroupByRow", row_class_names(panel.groupby_container_layout))
        self.assertNotIn("OrderByRow", row_class_names(panel.orderby_container_layout))

    def test_limit_input_allows_at_most_1000_rows(self) -> None:
        panel = VisualQueryBuilderPanel()
        validator = panel.limit_input.validator()

        self.assertIsNotNone(validator)
        self.assertEqual(validator.validate("1000", 4)[0], QValidator.State.Acceptable)
        self.assertEqual(validator.validate("1001", 4)[0], QValidator.State.Invalid)

        panel.set_schema([TableInfo("users", [ColumnInfo("id", "INT")])], {})
        panel.limit_input.setText("25")

        self.assertIn("LIMIT 25", panel.sql_editor.toPlainText())
