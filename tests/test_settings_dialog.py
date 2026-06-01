"""Smoke tests for SettingsDialog that covers AI settings and Schema Annotation widgets."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402

from sqlbot_desktop.models.entities import AIBackend, AIModelConfig, TableInfo, ColumnInfo  # noqa: E402
from sqlbot_desktop.utils.i18n_manager import set_language  # noqa: E402
from sqlbot_desktop.views.dialogs.settings_dialog import SettingsDialog  # noqa: E402
from sqlbot_desktop.views.dialogs.schema_annotation_dialog import SchemaAnnotationDialog  # noqa: E402


class SettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        set_language("vi")

    def test_threads_setting_explains_worker_threads_not_cpu_cap(self) -> None:
        dialog = SettingsDialog(
            config=AIModelConfig(backend=AIBackend.LOCAL, threads=4),
            connection_name="test_conn",
            tables=[]
        )
        ai_w = dialog.ai_widget

        self.assertEqual(ai_w.threads_label.text(), "Luồng suy luận LLM")
        self.assertIn("worker thread llama.cpp", ai_w.threads_spin.toolTip())
        self.assertIn("không phải giới hạn", ai_w.threads_hint.text())
        self.assertIn("Luồng suy luận LLM: 4", ai_w.resource_info.text())

    def test_defaults_match_cpu_only_laptop_profile(self) -> None:
        dialog = SettingsDialog(
            config=AIModelConfig(backend=AIBackend.LOCAL),
            connection_name="test_conn",
            tables=[]
        )
        ai_w = dialog.ai_widget
        config = ai_w.config()

        self.assertEqual(config.context_size, 2048)
        self.assertEqual(config.threads, 2)
        self.assertEqual(config.gpu_layers, 0)
        self.assertEqual(config.cpu_thread_limit, 4)
        self.assertEqual(config.self_correction_retries, 3)
        self.assertIn("Giới hạn app: 4", ai_w.resource_info.text())

    def test_self_correction_retries_round_trip(self) -> None:
        dialog = SettingsDialog(
            config=AIModelConfig(backend=AIBackend.API, self_correction_retries=5),
            connection_name="test_conn",
            tables=[]
        )
        ai_w = dialog.ai_widget

        self.assertEqual(ai_w.self_correction_spin.value(), 5)
        self.assertEqual(ai_w.config().self_correction_retries, 5)

    def test_api_key_round_trip(self) -> None:
        dialog = SettingsDialog(
            config=AIModelConfig(backend=AIBackend.API, api_key="secret-token-123"),
            connection_name="test_conn",
            tables=[]
        )
        ai_w = dialog.ai_widget

        self.assertEqual(ai_w.api_key_input.text(), "secret-token-123")
        self.assertEqual(ai_w.config().api_key, "secret-token-123")

    def test_navigation_switches_stacked_pages(self) -> None:
        dialog = SettingsDialog(
            config=AIModelConfig(backend=AIBackend.LOCAL),
            connection_name="test_conn",
            tables=[]
        )
        self.assertEqual(dialog.stack.currentIndex(), 0)
        dialog.nav_list.setCurrentRow(1)
        self.assertEqual(dialog.stack.currentIndex(), 1)
        self.assertEqual(dialog.nav_list.item(0).text(), "Cài đặt AI")
        self.assertEqual(dialog.nav_list.item(1).text(), "Chú thích CSDL")
        self.assertEqual(dialog.nav_list.count(), 2)

    def test_settings_dialog_does_not_expose_it_settings(self) -> None:
        dialog = SettingsDialog(
            config=AIModelConfig(backend=AIBackend.LOCAL),
            connection_name="test_conn",
            tables=[]
        )

        nav_items = [dialog.nav_list.item(i).text() for i in range(dialog.nav_list.count())]
        self.assertNotIn("Cài đặt IT", nav_items)
        self.assertFalse(hasattr(dialog, "it_widget"))

    def test_schema_annotation_dirty_state(self) -> None:
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT"), ColumnInfo("name", "VARCHAR")])
        ]
        dialog = SettingsDialog(
            config=AIModelConfig(backend=AIBackend.LOCAL),
            connection_name="test_conn",
            tables=tables
        )
        schema_w = dialog.schema_widget
        self.assertFalse(schema_w.is_dirty())

        # Simulate editing description
        top_item = schema_w.tree.topLevelItem(0)
        top_item.setText(1, "Người dùng")
        self.assertTrue(schema_w.is_dirty())

    def test_schema_annotation_selection_and_form_sync(self) -> None:
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT"), ColumnInfo("name", "VARCHAR")])
        ]
        dialog = SettingsDialog(
            config=AIModelConfig(backend=AIBackend.LOCAL),
            connection_name="test_conn",
            tables=tables
        )
        schema_w = dialog.schema_widget
        self.assertEqual(schema_w.detail_stack.currentIndex(), 0)

        # Select table
        top_item = schema_w.tree.topLevelItem(0)
        schema_w.tree.setCurrentItem(top_item)
        self.assertEqual(schema_w.detail_stack.currentIndex(), 1)
        self.assertEqual(schema_w.table_title_label.text(), "Bảng: users")

        # Edit table description
        schema_w.table_desc_edit.setText("Bảng người dùng hệ thống")
        self.assertEqual(top_item.text(1), "Bảng người dùng hệ thống")
        self.assertTrue(schema_w.is_dirty())

        # Select column
        col_item = top_item.child(0)
        schema_w.tree.setCurrentItem(col_item)
        self.assertEqual(schema_w.detail_stack.currentIndex(), 2)
        self.assertEqual(schema_w.column_title_label.text(), "Cột: users.id")
        self.assertIn("INT", schema_w.column_type_label.text())

        # Edit column description, unit, and note
        schema_w.column_desc_edit.setText("Mã người dùng")
        schema_w.column_unit_edit.setText("đơn vị")
        schema_w.column_note_edit.setPlainText("Chỉ dùng số nguyên")
        self.assertEqual(col_item.text(1), "Mã người dùng")
        self.assertEqual(col_item.text(2), "đơn vị")
        self.assertEqual(col_item.text(3), "Chỉ dùng số nguyên")

    def test_schema_annotation_search_filter(self) -> None:
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT"), ColumnInfo("name", "VARCHAR")]),
            TableInfo("orders", [ColumnInfo("amount", "DECIMAL")])
        ]
        dialog = SettingsDialog(
            config=AIModelConfig(backend=AIBackend.LOCAL),
            connection_name="test_conn",
            tables=tables
        )
        schema_w = dialog.schema_widget

        # Setup descriptions
        schema_w.tree.topLevelItem(0).setText(1, "Thông tin thành viên") # users description
        schema_w.tree.topLevelItem(0).child(1).setText(1, "Họ và tên") # users.name description

        # Search for "thành viên" (should match table 'users' description)
        schema_w.search_input.setText("thành viên")
        self.assertFalse(schema_w.tree.topLevelItem(0).isHidden())
        self.assertTrue(schema_w.tree.topLevelItem(1).isHidden())

        # Search for "amount" (should match column 'amount' in 'orders')
        schema_w.search_input.setText("amount")
        self.assertTrue(schema_w.tree.topLevelItem(0).isHidden())
        self.assertFalse(schema_w.tree.topLevelItem(1).isHidden())
        self.assertFalse(schema_w.tree.topLevelItem(1).child(0).isHidden())

        # Search for non-existent text
        schema_w.search_input.setText("xyz123")
        self.assertTrue(schema_w.tree.topLevelItem(0).isHidden())
        self.assertTrue(schema_w.tree.topLevelItem(1).isHidden())

    def test_schema_annotation_dialog_wrapper(self) -> None:
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT")])
        ]
        dialog = SchemaAnnotationDialog(
            connection_name="test_conn",
            tables=tables
        )
        # Verify it wraps SchemaAnnotationWidget and has close button
        self.assertIsNotNone(dialog.widget)
        self.assertTrue(dialog.widget._show_close_button)


if __name__ == "__main__":
    unittest.main()
