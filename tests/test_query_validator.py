"""Tests for SELECT-only SQL safety guards."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.infrastructure.database_manager import DatabaseManager  # noqa: E402
from sqlbot_desktop.services.query_validator import QueryValidator  # noqa: E402


class QueryValidatorTests(unittest.TestCase):
    def test_allows_plain_select_and_leading_comments(self) -> None:
        self.assertTrue(QueryValidator.is_readonly_select("SELECT id, name FROM users;"))
        self.assertTrue(QueryValidator.is_readonly_select("-- report\nSELECT * FROM users"))
        self.assertTrue(QueryValidator.is_readonly_select("/* report */ SELECT * FROM users"))

    def test_rejects_mutating_statements(self) -> None:
        unsafe_sql = [
            "INSERT INTO users(name) VALUES ('A')",
            "UPDATE users SET name = 'A'",
            "DELETE FROM users",
            "DROP TABLE users",
            "ALTER TABLE users ADD COLUMN age INT",
            "CREATE TABLE users (id INT)",
            "TRUNCATE TABLE users",
            "MERGE INTO users USING temp_users ON users.id = temp_users.id",
            "EXEC refresh_users",
            "GRANT SELECT ON users TO demo",
            "REVOKE SELECT ON users FROM demo",
        ]

        for sql in unsafe_sql:
            with self.subTest(sql=sql):
                self.assertFalse(QueryValidator.is_readonly_select(sql))

    def test_rejects_dangerous_keywords_after_select(self) -> None:
        unsafe_sql = [
            "SELECT * FROM users; DROP TABLE users;",
            "SELECT * FROM users; UPDATE users SET name = 'A';",
            "SELECT * FROM users WHERE id IN (DELETE FROM audit)",
        ]

        for sql in unsafe_sql:
            with self.subTest(sql=sql):
                self.assertFalse(QueryValidator.is_readonly_select(sql))

    def test_allows_semicolon_inside_string_literal(self) -> None:
        self.assertTrue(QueryValidator.is_readonly_select("SELECT 'a;b' AS label;"))
        self.assertTrue(QueryValidator.is_readonly_select("SELECT * FROM users WHERE status = 'deleted';"))

    def test_cte_is_not_supported_in_phase_zero(self) -> None:
        self.assertFalse(QueryValidator.is_readonly_select("WITH recent AS (SELECT 1) SELECT * FROM recent;"))

    def test_filter_readonly_keeps_only_safe_selects(self) -> None:
        queries = [
            "SELECT * FROM users;",
            "DELETE FROM users;",
            "SELECT * FROM orders;",
        ]

        self.assertEqual(
            QueryValidator.filter_readonly(queries),
            ["SELECT * FROM users;", "SELECT * FROM orders;"],
        )


class DatabaseManagerSelectGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        self.connection = engine.connect()
        self.connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
        self.connection.execute(text("INSERT INTO users (name) VALUES ('Lan')"))
        self.manager = DatabaseManager()
        self.manager._engines["test"] = engine
        self.manager._connections["test"] = self.connection
        self.manager.active_connection_name = "test"

    def tearDown(self) -> None:
        self.manager.close_connection("test")

    def test_execute_select_runs_safe_select(self) -> None:
        result = self.manager.execute_select("SELECT id, name FROM users;")

        self.assertTrue(result.ok)
        self.assertEqual(result.columns, ["id", "name"])
        self.assertEqual(result.rows, [[1, "Lan"]])
        self.assertEqual(result.row_count, 1)
        self.assertGreaterEqual(result.elapsed_ms, 0)
        self.assertEqual(result.sql, "SELECT id, name FROM users;")
        self.assertEqual(result.error_type, "")

    def test_execute_select_respects_max_rows(self) -> None:
        self.connection.execute(text("INSERT INTO users (name) VALUES ('Minh')"))

        result = self.manager.execute_select("SELECT id, name FROM users ORDER BY id;", max_rows=1)

        self.assertTrue(result.ok)
        self.assertEqual(result.rows, [[1, "Lan"]])
        self.assertEqual(result.row_count, 1)

    def test_execute_select_rejects_non_select(self) -> None:
        result = self.manager.execute_select("DELETE FROM users;")

        self.assertFalse(result.ok)
        self.assertIn("SELECT", result.message)
        self.assertEqual(result.error_type, "validation")
        self.assertEqual(result.sql, "DELETE FROM users;")

    def test_execute_select_rejects_stacked_statement(self) -> None:
        result = self.manager.execute_select("SELECT * FROM users; DROP TABLE users;")

        self.assertFalse(result.ok)
        self.assertIn("SELECT", result.message)
        self.assertEqual(result.error_type, "validation")

    def test_execute_select_returns_sql_error_result(self) -> None:
        result = self.manager.execute_select("SELECT missing_column FROM users;")

        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "sql")
        self.assertIn("missing_column", result.message)


if __name__ == "__main__":
    unittest.main()
