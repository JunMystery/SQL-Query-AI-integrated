import unittest
from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.agents.schema_graph import SchemaGraph
from sqlbot_desktop.agents.join_planner import JoinPlanner


class TestJoinPlanner(unittest.TestCase):
    """Verify that JoinPlanner correctly formats SQL joins and assigns table aliases."""

    def setUp(self) -> None:
        # Create standard tables with nullable properties to test joins
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
                    # Nullable FK column triggers LEFT JOIN by default
                    ColumnInfo("user_id", "INTEGER", is_foreign=True, nullable=True),
                ],
                foreign_keys=[{
                    "constrained_table": "orders",
                    "constrained_column": "user_id",
                    "referred_table": "users",
                    "referred_column": "id"
                }]
            ),
            TableInfo(
                name="payments",
                columns=[
                    ColumnInfo("id", "INTEGER", is_primary=True, nullable=False),
                    # Non-nullable FK column triggers INNER JOIN by default
                    ColumnInfo("order_id", "INTEGER", is_foreign=True, nullable=False),
                ],
                foreign_keys=[{
                    "constrained_table": "payments",
                    "constrained_column": "order_id",
                    "referred_table": "orders",
                    "referred_column": "id"
                }]
            )
        ]
        self.graph = SchemaGraph(self.tables)
        self.planner = JoinPlanner(self.graph)

    def test_alias_generation(self) -> None:
        aliases = self.planner.generate_aliases(["users", "orders", "order_items", "updates"])
        self.assertEqual(aliases["users"], "u")
        self.assertEqual(aliases["orders"], "o")
        self.assertEqual(aliases["order_items"], "oi")
        self.assertEqual(aliases["updates"], "u1")  # Collides with users -> u1

    def test_plan_joins_default_nullable(self) -> None:
        # Join users -> orders -> payments
        plan = self.planner.plan_joins("users", ["payments"])
        
        # Verify aliases mapping
        self.assertEqual(plan["aliases"]["users"], "u")
        self.assertEqual(plan["aliases"]["orders"], "o")
        self.assertEqual(plan["aliases"]["payments"], "p")

        # Verify join clauses:
        # 1. users -> orders join should be LEFT because user_id in orders is nullable=True
        # 2. orders -> payments join should be LEFT because payments is child of orders (Cha -> Con)
        clauses = plan["join_clauses"]
        self.assertEqual(len(clauses), 2)
        self.assertIn("LEFT JOIN orders o ON u.id = o.user_id", clauses)
        self.assertIn("LEFT JOIN payments p ON o.id = p.order_id", clauses)

    def test_plan_joins_con_to_cha(self) -> None:
        # Join payments -> orders -> users
        plan = self.planner.plan_joins("payments", ["users"])
        clauses = plan["join_clauses"]
        # Verify: payments -> orders is Con -> Cha and not nullable, so INNER JOIN
        # orders -> users is Con -> Cha and nullable, so LEFT JOIN
        self.assertIn("INNER JOIN orders o ON p.order_id = o.id", clauses)
        self.assertIn("LEFT JOIN users u ON o.user_id = u.id", clauses)

    def test_plan_joins_override(self) -> None:
        # Override to force INNER JOIN on orders
        plan = self.planner.plan_joins("users", ["payments"], join_types_override={"orders": "INNER"})
        clauses = plan["join_clauses"]
        self.assertIn("INNER JOIN orders o ON u.id = o.user_id", clauses)


if __name__ == "__main__":
    unittest.main()
