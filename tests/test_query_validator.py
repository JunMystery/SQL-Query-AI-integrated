"""Tests for SELECT-only SQL safety guards."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.infrastructure.database_manager import DatabaseManager, MAX_QUERY_ROWS  # noqa: E402
from sqlbot_desktop.services.query_validator import QueryValidator  # noqa: E402


class FakeDialect:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeEngine:
    def __init__(self, dialect_name: str) -> None:
        self.dialect = FakeDialect(dialect_name)


class FakeResult:
    def keys(self):
        return ["id"]

    def fetchmany(self, max_rows: int):
        return [(1,)]


class FakeConnection:
    def __init__(self, dialect_name: str) -> None:
        self.engine = FakeEngine(dialect_name)
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return FakeResult()


class TimeoutConnection(FakeConnection):
    def execute(self, statement):
        self.statements.append(str(statement))
        raise SQLAlchemyError("canceling statement due to statement timeout")


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
            "SELECT * FROM users -- WHERE id = 1",
            "SELECT * FROM users /* hidden predicate */",
            "SELECT * FROM users WHERE name = 'Lan",
            "SELECT * FROM users WHERE id = 1 /*",
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

    def test_execute_select_defaults_to_max_1000_rows(self) -> None:
        for index in range(MAX_QUERY_ROWS + 5):
            self.connection.execute(text("INSERT INTO users (name) VALUES (:name)"), {"name": f"User {index}"})

        result = self.manager.execute_select("SELECT id, name FROM users ORDER BY id;")

        self.assertTrue(result.ok)
        self.assertEqual(result.row_count, MAX_QUERY_ROWS)

    def test_execute_select_clamps_requested_max_rows_to_1000(self) -> None:
        for index in range(MAX_QUERY_ROWS + 5):
            self.connection.execute(text("INSERT INTO users (name) VALUES (:name)"), {"name": f"User {index}"})

        result = self.manager.execute_select("SELECT id, name FROM users ORDER BY id;", max_rows=5000)

        self.assertTrue(result.ok)
        self.assertEqual(result.row_count, MAX_QUERY_ROWS)

    def test_execute_select_wraps_existing_large_limit(self) -> None:
        for index in range(MAX_QUERY_ROWS + 5):
            self.connection.execute(text("INSERT INTO users (name) VALUES (:name)"), {"name": f"User {index}"})

        result = self.manager.execute_select("SELECT id, name FROM users ORDER BY id LIMIT 5000;")

        self.assertTrue(result.ok)
        self.assertEqual(result.row_count, MAX_QUERY_ROWS)

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

    def test_execute_select_sets_postgres_statement_timeout(self) -> None:
        connection = FakeConnection("postgresql")
        self.manager._connections["postgres"] = connection

        result = self.manager.execute_select("SELECT id FROM users;", "postgres")

        self.assertTrue(result.ok)
        self.assertEqual(connection.statements[0], "SET LOCAL statement_timeout = 10000")
        self.assertEqual(
            connection.statements[1],
            "SELECT * FROM (SELECT id FROM users) AS sqlbot_limited LIMIT 1000",
        )

    def test_execute_select_adds_mysql_execution_time_hint(self) -> None:
        connection = FakeConnection("mysql")
        self.manager._connections["mysql"] = connection

        result = self.manager.execute_select("SELECT id FROM users;", "mysql")

        self.assertTrue(result.ok)
        self.assertEqual(
            connection.statements[0],
            "SELECT /*+ MAX_EXECUTION_TIME(10000) */ * FROM (SELECT id FROM users) AS sqlbot_limited LIMIT 1000",
        )

    def test_execute_select_maps_timeout_errors(self) -> None:
        connection = TimeoutConnection("mysql")
        self.manager._connections["timeout"] = connection

        result = self.manager.execute_select("SELECT id FROM users;", "timeout")

        self.assertFalse(result.ok)
        self.assertEqual(result.error_type, "timeout")


if __name__ == "__main__":
    unittest.main()
