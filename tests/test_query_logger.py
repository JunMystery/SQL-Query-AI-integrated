"""Tests for self-correction query attempt logging."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.services.query_logger import QueryAttempt, QueryLogger  # noqa: E402


class QueryLoggerTests(unittest.TestCase):
    def test_log_attempt_writes_jsonl_without_connection_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = QueryLogger(Path(temp_dir)).log_attempt(
                QueryAttempt(
                    question="Lay user",
                    attempt=2,
                    sql="SELECT id FROM users;",
                    error="",
                    success=True,
                )
            )
            payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(payload["question"], "Lay user")
        self.assertEqual(payload["attempt"], 2)
        self.assertEqual(payload["sql"], "SELECT id FROM users;")
        self.assertTrue(payload["success"])
        self.assertNotIn("connection", payload)
        self.assertNotIn("password", payload)


if __name__ == "__main__":
    unittest.main()
