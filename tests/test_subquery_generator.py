import unittest
from sqlbot_desktop.agents.subquery_generator import SubqueryGenerator


class TestSubqueryGenerator(unittest.TestCase):
    """Verify SubqueryGenerator correctly parses prompts and wraps subqueries."""

    def test_detect_subquery_need_scalar_avg(self) -> None:
        prompt = "Hiển thị nhân viên có lương lớn hơn trung bình của phòng ban"
        detected = SubqueryGenerator.detect_subquery_need(prompt)
        self.assertIsNotNone(detected)
        self.assertEqual(detected["pattern"], "scalar_compare")
        self.assertEqual(detected["agg_func"], "AVG")

    def test_detect_subquery_need_not_in(self) -> None:
        prompt = "Lấy khách hàng chưa từng mua sản phẩm nào"
        detected = SubqueryGenerator.detect_subquery_need(prompt)
        self.assertIsNotNone(detected)
        self.assertEqual(detected["pattern"], "not_in")

    def test_generate_and_wrap_subquery_scalar(self) -> None:
        subquery = SubqueryGenerator.generate_subquery(
            pattern="scalar_compare",
            table="employees",
            column="salary",
            agg_func="AVG"
        )
        self.assertEqual(subquery, "(SELECT AVG(salary) FROM employees)")

        full_sql = SubqueryGenerator.wrap_query(
            outer_select="name, salary",
            outer_table="employees",
            condition_column="salary",
            operator=">",
            subquery_sql=subquery
        )
        self.assertEqual(
            full_sql,
            "SELECT name, salary FROM employees WHERE salary > (SELECT AVG(salary) FROM employees)"
        )


if __name__ == "__main__":
    unittest.main()
