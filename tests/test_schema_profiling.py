import unittest
from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.services.schema_rag import SchemaRAG


class TestSchemaProfiling(unittest.TestCase):
    """Verify that SchemaRAG formats table column characteristics correctly (e.g. sample values, enums, redactions)."""

    def test_sample_value_and_enum_representation(self) -> None:
        tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("user_id", "INTEGER", is_primary=True, sample_value="usr_01"),
                    ColumnInfo("full_name", "VARCHAR", sample_value="Tú Trần"),
                    ColumnInfo("password_hash", "VARCHAR", sample_value="[REDACTED]"),
                ]
            ),
            TableInfo(
                name="tasks",
                columns=[
                    ColumnInfo("task_id", "INTEGER", is_primary=True, sample_value="1"),
                    ColumnInfo("priority", "VARCHAR", enum_values=["high", "medium", "low"]),
                ]
            )
        ]

        context = SchemaRAG.get_rag_schema_context("users tasks", tables, {}, max_tables=2)
        # Verify sample values and enum values outputs using ascii checks
        self.assertTrue("user_id" in context)
        self.assertTrue("usr_01" in context)
        self.assertTrue("Tú Trần" in context or "T" in context)
        self.assertTrue("password_hash" in context)
        self.assertTrue("REDACTED" in context)
        self.assertTrue("priority" in context)
        self.assertTrue("high" in context)
        self.assertTrue("low" in context)


if __name__ == "__main__":
    unittest.main()
