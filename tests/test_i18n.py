"""Tests for multi-language (i18n) translation functionality."""

from __future__ import annotations
import unittest
from sqlbot_desktop.utils.i18n_manager import tr, set_language, get_current_language


class TestI18n(unittest.TestCase):
    """Verify localization translation keys are loaded and return active values."""

    def test_i18n_translation_loading(self) -> None:
        # Load and verify Vietnamese translations
        set_language("vi")
        self.assertEqual(get_current_language(), "vi")
        self.assertEqual(tr("main.app_title"), "SQLBot Workspace")
        self.assertEqual(tr("main.chat_btn_send"), "Gửi yêu cầu")
        self.assertEqual(tr("query_builder.checkbox_distinct"), "Loại bỏ trùng lặp")
        self.assertEqual(tr("query_builder.btn_columns_order_short"), "Thứ tự")

        # Load and verify English translations
        set_language("en")
        self.assertEqual(get_current_language(), "en")
        self.assertEqual(tr("main.app_title"), "SQLBot Workspace")
        self.assertEqual(tr("main.chat_btn_send"), "Send Request")
        self.assertEqual(tr("query_builder.checkbox_distinct"), "Remove duplicates")
        self.assertEqual(tr("query_builder.btn_columns_order_short"), "Order")

        # Load and verify Japanese translations
        set_language("jp")
        self.assertEqual(get_current_language(), "jp")
        self.assertEqual(tr("main.app_title"), "SQLBot ワークスペース")
        self.assertEqual(tr("main.chat_btn_send"), "要求を送信")
        self.assertEqual(tr("query_builder.checkbox_distinct"), "重複を排除する")
        self.assertEqual(tr("query_builder.btn_columns_order_short"), "順序")

    def test_i18n_fallback(self) -> None:
        # Fallback to key or default when key is missing
        self.assertEqual(tr("nonexistent_key_prefix.my_key"), "nonexistent_key_prefix.my_key")
        self.assertEqual(tr("nonexistent_key_prefix.my_key", "Default Value"), "Default Value")


if __name__ == "__main__":
    unittest.main()
