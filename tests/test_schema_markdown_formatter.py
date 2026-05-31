"""Tests for schema metadata Markdown formatting."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.models.entities import ColumnMetadata  # noqa: E402
from sqlbot_desktop.services.schema_markdown_formatter import SchemaMarkdownFormatter  # noqa: E402


class SchemaMarkdownFormatterTests(unittest.TestCase):
    def test_formats_columns_grouped_by_table(self) -> None:
        markdown = SchemaMarkdownFormatter.format(
            [
                ColumnMetadata("demo", "orders", "id", "INTEGER", is_primary_key=True),
                ColumnMetadata(
                    "demo",
                    "orders",
                    "user_id",
                    "INTEGER",
                    is_foreign_key=True,
                    referenced_table="users",
                    referenced_column="id",
                ),
                ColumnMetadata(
                    "demo",
                    "users",
                    "status",
                    "TEXT",
                    business_description="Trạng thái tài khoản",
                    sample_values=["active", "locked", "pending", "archived"],
                ),
            ]
        )

        self.assertIn("## Table: orders", markdown)
        self.assertIn("- id (INTEGER, PK)", markdown)
        self.assertIn("- user_id (INTEGER, FK -> users.id)", markdown)
        self.assertIn("## Table: users", markdown)
        self.assertIn("Trạng thái tài khoản", markdown)
        self.assertIn("ví dụ: 'active', 'locked', 'pending'", markdown)
        self.assertNotIn("archived", markdown)

    def test_empty_schema_returns_empty_string(self) -> None:
        self.assertEqual(SchemaMarkdownFormatter.format([]), "")


if __name__ == "__main__":
    unittest.main()
