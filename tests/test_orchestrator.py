import unittest
from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.agents.orchestrator import Orchestrator


class TestOrchestrator(unittest.TestCase):
    """Verify Orchestrator coordinates router, planner, classifiers, aggregations, and validators."""

    def test_orchestrate_simple_aggregate_query(self) -> None:
        tables = [
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

        orchestrator = Orchestrator(tables, dialect="sqlite")
        sql = orchestrator.orchestrate(
            question="Tổng tiền mua hàng của từng user có tổng mua hàng hơn 100",
            start_table="users",
            target_tables=["orders"],
            select_columns=["id", "name", "SUM(orders.amount) AS total"],
            filter_expression="SUM(orders.amount) > 100"
        )

        # Expected output includes aggregate group-by, join, and having:
        # SELECT u.id, u.name, SUM(o.amount) AS total
        # FROM users u
        # INNER JOIN orders o ON u.id = o.user_id
        # GROUP BY u.id, u.name
        # HAVING SUM(o.amount) > 100
        
        self.assertIn("SELECT", sql)
        self.assertIn("FROM users u", sql)
        self.assertIn("LEFT JOIN orders o ON u.id = o.user_id", sql)
        self.assertIn("GROUP BY u.id, u.name", sql)
        self.assertIn("HAVING SUM(o.amount) > 100", sql)

    def test_orchestrate_new_features(self) -> None:
        tables = [
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True, nullable=False),
                    ColumnInfo("name", "VARCHAR", nullable=False),
                ]
            )
        ]

        # SQLite/MySQL: should use LIMIT
        orchestrator_sqlite = Orchestrator(tables, dialect="sqlite")
        sql_sqlite = orchestrator_sqlite._build_single_query(
            start_table="users",
            target_tables=[],
            select_columns=["id", "name"],
            filter_expression="EXISTS (SELECT 1 FROM orders WHERE orders.user_id = users.id)",
            group_by_columns=["users.id", "users.name"],
            order_by_columns=["users.name DESC"],
            limit_count=10
        )
        self.assertIn("GROUP BY u.id, u.name", sql_sqlite)
        self.assertIn("ORDER BY u.name DESC", sql_sqlite)
        self.assertIn("EXISTS (SELECT 1 FROM orders WHERE orders.user_id = users.id)", sql_sqlite)
        self.assertIn("LIMIT 10", sql_sqlite)

        # MSSQL: should use TOP
        orchestrator_mssql = Orchestrator(tables, dialect="mssql")
        sql_mssql = orchestrator_mssql._build_single_query(
            start_table="users",
            target_tables=[],
            select_columns=["id", "name"],
            filter_expression="NOT EXISTS (SELECT 1 FROM orders WHERE orders.user_id = users.id)",
            group_by_columns=["users.id"],
            order_by_columns=["users.name ASC"],
            limit_count=50
        )
        self.assertTrue(sql_mssql.startswith("SELECT TOP 50 u.id, u.name"))
        self.assertIn("GROUP BY u.id", sql_mssql)
        self.assertIn("ORDER BY u.name ASC", sql_mssql)
        self.assertIn("NOT EXISTS (SELECT 1 FROM orders WHERE orders.user_id = users.id)", sql_mssql)
        self.assertNotIn("LIMIT", sql_mssql)


if __name__ == "__main__":
    unittest.main()
