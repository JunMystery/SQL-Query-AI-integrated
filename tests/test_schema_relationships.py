import unittest
from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.services.schema_rag import SchemaRAG


class TestSchemaRelationships(unittest.TestCase):
    """Verify that SchemaRAG properly extracts and presents logical and physical relationships."""

    def setUp(self) -> None:
        self.tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("user_id", "INTEGER", is_primary=True),
                    ColumnInfo("full_name", "VARCHAR"),
                ]
            ),
            TableInfo(
                name="tasks",
                columns=[
                    ColumnInfo("task_id", "INTEGER", is_primary=True),
                    ColumnInfo("user_id", "INTEGER", is_foreign=True),
                    ColumnInfo("title", "VARCHAR"),
                ],
                foreign_keys=[{
                    "constrained_table": "tasks",
                    "constrained_column": "user_id",
                    "referred_table": "users",
                    "referred_column": "user_id"
                }]
            )
        ]

    def test_physical_foreign_keys_present(self) -> None:
        # Physical relationships are present
        context = SchemaRAG.get_rag_schema_context("hiển thị tasks của user", self.tables, {}, max_tables=2)
        self.assertIn("tasks", context)
        self.assertIn("users", context)
        self.assertIn("user_id (FK)", context)
        self.assertIn("user_id (PK)", context)
        self.assertIn("Bảng `tasks` (cột `user_id`) -> Bảng `users` (cột `user_id`)", context)

    def test_logical_foreign_keys_fallback(self) -> None:
        # Erase physical foreign keys to test logical fallback
        tables_logical = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("user_id", "INTEGER", is_primary=True),
                    ColumnInfo("full_name", "VARCHAR"),
                ]
            ),
            TableInfo(
                name="tasks",
                columns=[
                    ColumnInfo("task_id", "INTEGER", is_primary=True),
                    ColumnInfo("user_id", "INTEGER"),
                    ColumnInfo("title", "VARCHAR"),
                ],
                foreign_keys=[]
            )
        ]
        context = SchemaRAG.get_rag_schema_context("hiển thị tasks của user", tables_logical, {}, max_tables=2)
        self.assertIn("tasks", context)
        self.assertIn("users", context)
        self.assertIn("Bảng `tasks` (cột `user_id`) -> Bảng `users` (cột `user_id`)", context)


if __name__ == "__main__":
    unittest.main()
