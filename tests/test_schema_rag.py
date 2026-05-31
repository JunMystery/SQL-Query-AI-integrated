"""Unit tests for the SchemaRAG lookup service."""

from __future__ import annotations

import unittest

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.services.schema_rag import SchemaRAG


class TestSchemaRAG(unittest.TestCase):
    """Verify that SchemaRAG ranks relevant tables and filters schema contexts correctly."""

    def setUp(self) -> None:
        self.tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("user_id", "INTEGER"),
                    ColumnInfo("full_name", "VARCHAR"),
                    ColumnInfo("email", "VARCHAR"),
                ],
            ),
            TableInfo(
                name="habits",
                columns=[
                    ColumnInfo("habit_id", "INTEGER"),
                    ColumnInfo("user_id", "INTEGER"),
                    ColumnInfo("title", "VARCHAR"),
                    ColumnInfo("from_date", "DATE"),
                    ColumnInfo("to_date", "DATE"),
                ],
            ),
            TableInfo(
                name="diseases",
                columns=[
                    ColumnInfo("disease_id", "INTEGER"),
                    ColumnInfo("name", "VARCHAR"),
                ],
            ),
        ]
        self.annotations = {
            "tables": {
                "users": {"description": "Người dùng hệ thống"},
                "habits": {"description": "Thói quen hoạt động"},
            }
        }

    def test_synonym_expansion(self) -> None:
        keywords = SchemaRAG.get_keywords("Tính tổng số tasks thực hiện")
        self.assertIn("tasks", keywords)
        self.assertIn("habit", keywords)  # tasks synonym
        self.assertIn("completion", keywords)  # thực hiện synonym

    def test_rank_tables_by_tasks_and_user(self) -> None:
        prompt = "Tính tổng số Tasks mà người dùng Tú đã thực hiện từ ngày 01/05/2026 đến 10/05/2026"
        ranked = SchemaRAG.rank_tables(prompt, self.tables, self.annotations)
        
        # habits and users should rank higher than diseases
        self.assertTrue(len(ranked) >= 2)
        top_names = [t.name for t in ranked[:2]]
        self.assertIn("habits", top_names)
        self.assertIn("users", top_names)
        self.assertNotIn("diseases", top_names)

    def test_context_formatting(self) -> None:
        prompt = "Tính tổng số Tasks của user"
        # Re-set tables inside the test with keys
        self.tables[0] = TableInfo(
            name="users",
            columns=[
                ColumnInfo("user_id", "INTEGER", is_primary=True),
                ColumnInfo("full_name", "VARCHAR"),
                ColumnInfo("email", "VARCHAR"),
            ]
        )
        self.tables[1] = TableInfo(
            name="habits",
            columns=[
                ColumnInfo("habit_id", "INTEGER", is_primary=True),
                ColumnInfo("user_id", "INTEGER", is_foreign=True),
                ColumnInfo("title", "VARCHAR"),
                ColumnInfo("from_date", "DATE"),
                ColumnInfo("to_date", "DATE"),
            ],
            foreign_keys=[{
                "constrained_table": "habits",
                "constrained_column": "user_id",
                "referred_table": "users",
                "referred_column": "user_id"
            }]
        )
        context = SchemaRAG.get_rag_schema_context(prompt, self.tables, self.annotations, max_tables=2)
        # Avoid non-ascii characters in assertions if encoding mismatch is possible
        self.assertTrue("habits" in context)
        self.assertTrue("PK" in context)
        self.assertTrue("FK" in context)
        self.assertTrue("FOREIGN KEYS" in context)
        self.assertTrue("users" in context)


if __name__ == "__main__":
    unittest.main()
