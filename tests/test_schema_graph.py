import unittest
from sqlbot_desktop.models.entities import ColumnInfo, TableInfo, ColumnMetadata
from sqlbot_desktop.agents.schema_graph import SchemaGraph


class TestSchemaGraph(unittest.TestCase):
    """Verify that SchemaGraph correctly builds the in-memory graph and finds join paths."""

    def test_parse_table_info_with_explicit_keys(self) -> None:
        # Arrange
        tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True),
                    ColumnInfo("name", "VARCHAR"),
                ]
            ),
            TableInfo(
                name="orders",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True),
                    ColumnInfo("user_id", "INTEGER", is_foreign=True),
                ],
                foreign_keys=[{
                    "constrained_table": "orders",
                    "constrained_column": "user_id",
                    "referred_table": "users",
                    "referred_column": "id"
                }]
            ),
            TableInfo(
                name="order_items",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True),
                    ColumnInfo("order_id", "INTEGER", is_foreign=True),
                ],
                foreign_keys=[{
                    "constrained_table": "order_items",
                    "constrained_column": "order_id",
                    "referred_table": "orders",
                    "referred_column": "id"
                }]
            )
        ]

        # Act
        graph = SchemaGraph(tables)
        path = graph.find_join_path("users", ["order_items"])

        # Assert
        # Should find path: users -> orders -> order_items
        self.assertEqual(len(path), 2)
        # Verify the joins in sequence
        # Note: path can be traversed from start to end
        self.assertEqual(path[0][0], "users")
        self.assertEqual(path[0][2], "orders")
        self.assertEqual(path[1][0], "orders")
        self.assertEqual(path[1][2], "order_items")

    def test_parse_column_metadata_with_explicit_keys(self) -> None:
        # Arrange
        columns = [
            ColumnMetadata("db", "users", "id", "INTEGER", is_primary_key=True),
            ColumnMetadata("db", "users", "name", "VARCHAR"),
            ColumnMetadata("db", "orders", "id", "INTEGER", is_primary_key=True),
            ColumnMetadata("db", "orders", "user_id", "INTEGER", is_foreign_key=True, referenced_table="users", referenced_column="id"),
        ]

        # Act
        graph = SchemaGraph(columns)
        path = graph.find_join_path("users", ["orders"])

        # Assert
        self.assertEqual(len(path), 1)
        self.assertEqual(path[0], ("users", "id", "orders", "user_id"))

    def test_fallback_naming_convention_plural_singular(self) -> None:
        # Arrange
        # No explicit foreign keys defined, relying on naming fallback
        tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True),
                    ColumnInfo("name", "VARCHAR"),
                ]
            ),
            TableInfo(
                name="orders",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True),
                    ColumnInfo("user_id", "INTEGER"),
                ]
            )
        ]

        # Act
        graph = SchemaGraph(tables)
        path = graph.find_join_path("users", ["orders"])

        # Assert
        self.assertEqual(len(path), 1)
        # Should link users.id to orders.user_id using singular table name rule
        self.assertEqual(path[0], ("users", "id", "orders", "user_id"))

    def test_fallback_naming_convention_identical_id_columns(self) -> None:
        # Arrange
        tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("user_id", "INTEGER", is_primary=True),
                ]
            ),
            TableInfo(
                name="tasks",
                columns=[
                    ColumnInfo("task_id", "INTEGER", is_primary=True),
                    ColumnInfo("user_id", "INTEGER"),
                ]
            )
        ]

        # Act
        graph = SchemaGraph(tables)
        path = graph.find_join_path("users", ["tasks"])

        # Assert
        self.assertEqual(len(path), 1)
        self.assertEqual(path[0], ("users", "user_id", "tasks", "user_id"))

    def test_unreachable_table(self) -> None:
        # Arrange
        tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True),
                ]
            ),
            TableInfo(
                name="unrelated",
                columns=[
                    ColumnInfo("unrelated_id", "INTEGER", is_primary=True),
                ]
            )
        ]

        # Act
        graph = SchemaGraph(tables)
        path = graph.find_join_path("users", ["unrelated"])

        # Assert
        self.assertEqual(path, [])


if __name__ == "__main__":
    unittest.main()
