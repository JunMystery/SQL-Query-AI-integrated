import unittest
from unittest.mock import MagicMock
from sqlbot_desktop.agents.correction_loop import CorrectionLoop


class TestCorrectionLoop(unittest.TestCase):
    """Verify CorrectionLoop parses and validates queries correctly, calling the mock AI for fixes."""

    def test_validate_correct_sql(self) -> None:
        loop = CorrectionLoop()
        query = "SELECT id, name FROM users WHERE id = 1"
        res = loop.validate_and_correct(query, dialect="sqlite")
        self.assertEqual(res, query)

    def test_validate_incorrect_sql_fails_without_engine(self) -> None:
        loop = CorrectionLoop()
        # Invalid syntax query
        query = "SELECT id name FROM WHERE"
        res = loop.validate_and_correct(query, dialect="sqlite")
        self.assertEqual(res, query)  # Stays unchanged as there's no engine

    def test_validate_incorrect_sql_corrects_with_engine(self) -> None:
        # Mock engine to simulate correction
        mock_engine = MagicMock()
        mock_engine.is_loaded = True
        mock_engine.generate_chat_response.return_value = "```sql\nSELECT id, name FROM users\n```"

        loop = CorrectionLoop(ai_engine=mock_engine)
        query = "SELECT id name FROM WHERE"
        res = loop.validate_and_correct(query, dialect="sqlite")
        
        self.assertEqual(res.rstrip(";"), "SELECT id, name FROM users")
        mock_engine.generate_chat_response.assert_called_once()


if __name__ == "__main__":
    unittest.main()
