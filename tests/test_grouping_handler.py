import unittest
from sqlbot_desktop.agents.grouping_handler import GroupingHandler


class TestGroupingHandler(unittest.TestCase):
    """Verify GroupingHandler correctly appends GROUP BY columns and splits HAVING conditions."""

    def test_parse_group_by_with_aggregates(self) -> None:
        select_cols = ["user_id", "COUNT(id) AS total_orders", "status"]
        group_by = GroupingHandler.parse_group_by(select_cols)
        # Should identify non-aggregate columns: user_id and status (stripped of any AS aliases)
        self.assertEqual(group_by, ["user_id", "status"])

    def test_parse_group_by_no_aggregates(self) -> None:
        select_cols = ["user_id", "status", "name"]
        group_by = GroupingHandler.parse_group_by(select_cols)
        # Without aggregates in SELECT, no GROUP BY is generated
        self.assertEqual(group_by, [])

    def test_formulate_having(self) -> None:
        filters = ["SUM(amount) > 100", "status = 'active'", "AVG(price) < 500"]
        where_conds, having_conds = GroupingHandler.formulate_having(filters)

        self.assertEqual(where_conds, ["status = 'active'"])
        self.assertEqual(having_conds, ["SUM(amount) > 100", "AVG(price) < 500"])


if __name__ == "__main__":
    unittest.main()
