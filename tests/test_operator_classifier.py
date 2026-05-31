import unittest
from sqlbot_desktop.agents.operator_classifier import OperatorClassifier, ConditionNode, LogicalNode


class TestOperatorClassifier(unittest.TestCase):
    """Verify that OperatorClassifier classifies NL operators and parses condition expressions correctly."""

    def test_classify_operators(self) -> None:
        text = "Lấy các đơn hàng nằm trong khoảng từ ngày 1 đến ngày 10 và có giá trị rỗng"
        detected = OperatorClassifier.classify_operators(text)
        self.assertIn("BETWEEN", detected)
        self.assertIn("IS NULL", detected)

    def test_parse_simple_and_between(self) -> None:
        expr = "age BETWEEN 18 AND 30"
        node = OperatorClassifier.parse(expr)
        self.assertIsInstance(node, ConditionNode)
        self.assertEqual(node.column, "age")
        self.assertEqual(node.operator, "BETWEEN")
        self.assertEqual(node.values, ["18", "30"])

    def test_parse_logical_and(self) -> None:
        expr = "status IN ('active', 'pending') AND score > 50"
        node = OperatorClassifier.parse(expr)
        self.assertIsInstance(node, LogicalNode)
        self.assertEqual(node.connector, "AND")
        self.assertEqual(len(node.children), 2)
        
        left, right = node.children
        self.assertIsInstance(left, ConditionNode)
        self.assertEqual(left.column, "status")
        self.assertEqual(left.operator, "IN")
        self.assertEqual(left.values, ["'active'", "'pending'"])
        
        self.assertIsInstance(right, ConditionNode)
        self.assertEqual(right.column, "score")
        self.assertEqual(right.operator, ">")
        self.assertEqual(right.values, ["50"])

    def test_parse_exists(self) -> None:
        expr = "EXISTS (SELECT id FROM users)"
        node = OperatorClassifier.parse(expr)
        self.assertIsInstance(node, ConditionNode)
        self.assertEqual(node.column, "")
        self.assertEqual(node.operator, "EXISTS")
        self.assertEqual(node.values, ["SELECT id FROM users"])


if __name__ == "__main__":
    unittest.main()
