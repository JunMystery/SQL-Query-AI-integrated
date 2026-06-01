import unittest
from unittest.mock import MagicMock
from sqlbot_desktop.models.entities import ColumnInfo, TableInfo, GenerationResult
from sqlbot_desktop.agents.advanced_sql_agent import AdvancedSQLAgent


class TestAdvancedSQLAgent(unittest.TestCase):
    """Verify AdvancedSQLAgent handles intent parsing, orchestrator routing, and traditional text-to-SQL fallback."""

    def setUp(self) -> None:
        self.tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True, nullable=False),
                    ColumnInfo("name", "VARCHAR", nullable=False),
                ]
            ),
            TableInfo(
                name="orders",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True, nullable=False),
                    ColumnInfo("user_id", "INTEGER", is_foreign=True, nullable=False),
                    ColumnInfo("amount", "DECIMAL", nullable=False),
                ],
                foreign_keys=[{
                    "constrained_table": "orders",
                    "constrained_column": "user_id",
                    "referred_table": "users",
                    "referred_column": "id"
                }]
            )
        ]

    def test_generate_sql_via_structured_json(self) -> None:
        # Arrange
        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        mock_engine.generate_chat_response.return_value = (
            '{\n'
            '  "start_table": "users",\n'
            '  "target_tables": ["orders"],\n'
            '  "select_columns": ["id", "name", "SUM(orders.amount) AS total"],\n'
            '  "filter_expression": "SUM(orders.amount) > 100"\n'
            '}'
        )

        agent = AdvancedSQLAgent(ai_engine=mock_engine, metadata_list=self.tables)

        # Act
        sql = agent.generate_sql("Tổng mua hàng > 100")

        # Assert
        self.assertIn("SELECT u.id, u.name, SUM(o.amount) AS total", sql)
        self.assertIn("FROM users u LEFT JOIN orders o", sql)
        self.assertIn("GROUP BY u.id, u.name HAVING SUM(o.amount) > 100", sql)

    def test_generate_sql_fallback_on_json_failure(self) -> None:
        # Arrange
        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        # Return invalid JSON to trigger fallback
        mock_engine.generate_chat_response.return_value = "invalid response"
        mock_engine.generate.return_value = GenerationResult(
            ok=True,
            queries=["SELECT * FROM users;"]
        )

        agent = AdvancedSQLAgent(ai_engine=mock_engine, metadata_list=self.tables)

        # Act
        sql = agent.generate_sql("Lấy tất cả người dùng")

        # Assert
        self.assertEqual(sql, "SELECT * FROM users;")
        mock_engine.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
