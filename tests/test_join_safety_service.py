"""Tests for bounded JOIN safety checks."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.models.entities import ColumnInfo, TableInfo
from sqlbot_desktop.services.join_safety_service import JoinSafetyService


class JoinSafetyServiceTests(unittest.TestCase):
    def _close_connection(self, connection) -> None:
        engine = connection.engine
        connection.close()
        engine.dispose()

    def _tables(self) -> list[TableInfo]:
        return [
            TableInfo("users", [ColumnInfo("id", "INT", is_primary=True)]),
            TableInfo(
                "orders",
                [ColumnInfo("id", "INT", is_primary=True), ColumnInfo("user_id", "INT", is_foreign=True)],
                [{"constrained_table": "orders", "constrained_column": "user_id", "referred_table": "users", "referred_column": "id"}],
            ),
            TableInfo("audit_logs", [ColumnInfo("id", "INT", is_primary=True)]),
        ]

    def _connection(self, with_match: bool):
        engine = create_engine("sqlite:///:memory:")
        connection = engine.connect()
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER)"))
        connection.execute(text("INSERT INTO users (id) VALUES (1)"))
        user_id = 1 if with_match else 999
        connection.execute(text("INSERT INTO orders (id, user_id) VALUES (10, :user_id)"), {"user_id": user_id})
        return connection

    def test_no_fk_path_returns_danger_without_connection(self) -> None:
        class FailingConnection:
            def execute(self, statement):
                raise AssertionError("DB should not be queried without a JOIN path")

        service = JoinSafetyService()

        result = service.check_candidate("users", [], "audit_logs", self._tables(), connection=FailingConnection())

        self.assertFalse(result.ok)
        self.assertEqual(result.severity, "danger")
        self.assertEqual(result.join_edges, [])

    def test_fk_path_with_sample_match_returns_ok(self) -> None:
        service = JoinSafetyService(sample_limit=20)
        connection = self._connection(with_match=True)

        try:
            result = service.check_candidate("users", [], "orders", self._tables(), connection=connection)
        finally:
            self._close_connection(connection)

        self.assertTrue(result.ok)
        self.assertIn(result.severity, {"ok", "warning"})
        self.assertGreater(result.matched_sample_rows, 0)

    def test_fk_path_without_sample_match_returns_danger(self) -> None:
        service = JoinSafetyService(sample_limit=20)
        connection = self._connection(with_match=False)

        try:
            result = service.check_candidate("users", [], "orders", self._tables(), connection=connection)
        finally:
            self._close_connection(connection)

        self.assertFalse(result.ok)
        self.assertEqual(result.severity, "danger")
        self.assertEqual(result.matched_sample_rows, 0)

    def test_unsafe_identifier_returns_warning_not_crash(self) -> None:
        service = JoinSafetyService()
        tables = [
            TableInfo("users", [ColumnInfo("id", "INT", is_primary=True)]),
            TableInfo(
                "bad-name",
                [ColumnInfo("user_id", "INT", is_foreign=True)],
                [{"constrained_table": "bad-name", "constrained_column": "user_id", "referred_table": "users", "referred_column": "id"}],
            ),
        ]

        connection = self._connection(with_match=True)
        try:
            result = service.check_candidate("users", [], "bad-name", tables, connection=connection)
        finally:
            self._close_connection(connection)

        self.assertTrue(result.ok)
        self.assertEqual(result.severity, "warning")

    def test_db_probe_error_returns_warning(self) -> None:
        class FailingConnection:
            def execute(self, statement):
                raise RuntimeError("probe failed")

        service = JoinSafetyService()

        result = service.check_candidate("users", [], "orders", self._tables(), connection=FailingConnection())

        self.assertTrue(result.ok)
        self.assertEqual(result.severity, "warning")
        self.assertIn("probe failed", result.message)

    def test_cache_avoids_second_probe(self) -> None:
        service = JoinSafetyService(sample_limit=20)
        connection = self._connection(with_match=True)

        first = service.check_candidate("users", [], "orders", self._tables(), connection=connection)
        connection.close()
        second = service.check_candidate("users", [], "orders", self._tables(), connection=connection)
        connection.engine.dispose()

        self.assertEqual(second, first)


if __name__ == "__main__":
    unittest.main()
