"""Tests for extracting safe SELECT statements from LLM output."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.services.sql_extractor import SQLExtractor  # noqa: E402


class SQLExtractorTests(unittest.TestCase):
    def test_extracts_sql_fenced_select(self) -> None:
        raw = "```sql\nSELECT id, name FROM users;\n```"

        self.assertEqual(SQLExtractor.extract_select_queries(raw), ["SELECT id, name FROM users;"])

    def test_extracts_generic_fenced_select(self) -> None:
        raw = "```\nSELECT * FROM orders\n```"

        self.assertEqual(SQLExtractor.extract_select_queries(raw), ["SELECT * FROM orders;"])

    def test_extracts_plain_select_only_when_output_starts_with_select(self) -> None:
        self.assertEqual(SQLExtractor.extract_select_queries("SELECT 'a;b' AS value;"), ["SELECT 'a;b' AS value;"])
        self.assertEqual(SQLExtractor.extract_select_queries("Đây là SQL: SELECT * FROM users;"), [])

    def test_rejects_unsafe_or_stacked_statement(self) -> None:
        self.assertEqual(SQLExtractor.extract_select_queries("```sql\nDROP TABLE users;\n```"), [])
        self.assertEqual(SQLExtractor.extract_select_queries("```sql\nSELECT * FROM users; DROP TABLE users;\n```"), [])

    def test_limits_number_of_queries(self) -> None:
        raw = "\n".join(
            [
                "```sql\nSELECT * FROM users;\n```",
                "```sql\nSELECT * FROM orders;\n```",
                "```sql\nSELECT * FROM products;\n```",
            ]
        )

        self.assertEqual(len(SQLExtractor.extract_select_queries(raw, limit=2)), 2)


if __name__ == "__main__":
    unittest.main()
