"""Tests for fuzzy query corrector."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.services.query_corrector import QueryCorrector


class QueryCorrectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tables = [
            TableInfo(
                name="biometricreadings",
                columns=[
                    ColumnInfo("reading_id", "INTEGER", False),
                    ColumnInfo("user_id", "VARCHAR(16)", False),
                    ColumnInfo("recorded_at", "DATETIME", False),
                    ColumnInfo("value", "FLOAT", False),
                ]
            ),
            TableInfo(
                name="users",
                columns=[
                    ColumnInfo("user_id", "VARCHAR(16)", False),
                    ColumnInfo("full_name", "TEXT", False),
                    ColumnInfo("is_active", "TINYINT", False),
                ]
            )
        ]

    def test_correct_table_name_close_match(self) -> None:
        # User input: biometric_readings instead of biometricreadings
        sql = "SELECT user_id, value FROM biometric_readings WHERE value > 10;"
        corrected = QueryCorrector.correct_query(sql, self.tables)
        self.assertIn("FROM biometricreadings", corrected)
        self.assertNotIn("biometric_readings", corrected)

    def test_correct_column_name_close_match(self) -> None:
        # User input: recordedat instead of recorded_at, fullname instead of full_name
        sql = "SELECT user_id, recordedat FROM biometricreadings;"
        corrected = QueryCorrector.correct_query(sql, self.tables)
        self.assertIn("recorded_at", corrected)
        self.assertNotIn("recordedat", corrected)

    def test_correct_both_table_and_column_name(self) -> None:
        # User input: biometric_readings and recordedat
        sql = "SELECT user_id, recordedat FROM biometric_readings WHERE user_id = '123';"
        corrected = QueryCorrector.correct_query(sql, self.tables)
        self.assertIn("FROM biometricreadings", corrected)
        self.assertIn("recorded_at", corrected)
        self.assertNotIn("biometric_readings", corrected)
        self.assertNotIn("recordedat", corrected)

    def test_keywords_are_ignored(self) -> None:
        # Ensure select/from/where are not corrected
        sql = "SELECT user_id FROM users;"
        corrected = QueryCorrector.correct_query(sql, self.tables)
        self.assertEqual(sql, corrected)


if __name__ == "__main__":
    unittest.main()
