import unittest
from sqlbot_desktop.agents.setop_handler import SetOpHandler


class TestSetOpHandler(unittest.TestCase):
    """Verify SetOpHandler correctly detects set operators and stitches query parts."""

    def test_detect_set_op_union(self) -> None:
        self.assertEqual(SetOpHandler.detect_set_op("kết hợp tất cả các khách hàng"), "UNION ALL")
        self.assertEqual(SetOpHandler.detect_set_op("gộp danh sách a và b"), "UNION")
        self.assertEqual(SetOpHandler.detect_set_op("giao của hai danh sách"), "INTERSECT")
        self.assertEqual(SetOpHandler.detect_set_op("ngoại trừ các đơn hàng cũ"), "EXCEPT")
        self.assertIsNone(SetOpHandler.detect_set_op("lấy danh sách khách hàng mới"))

    def test_stitch_queries(self) -> None:
        queries = ["SELECT name FROM users;", "SELECT title FROM tasks"]
        stitched = SetOpHandler.stitch_queries(queries, "UNION")
        self.assertEqual(stitched, "SELECT name FROM users UNION SELECT title FROM tasks")


if __name__ == "__main__":
    unittest.main()
