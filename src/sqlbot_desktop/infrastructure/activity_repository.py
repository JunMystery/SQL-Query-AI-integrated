"""SQLite persistence for query history and bookmarks."""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterable, Iterator


@dataclass(frozen=True)
class HistoryEntry:
    id: int
    question: str
    sql: str
    timestamp: str
    is_success: bool


@dataclass(frozen=True)
class BookmarkEntry:
    id: int
    question: str
    sql: str
    timestamp: str
    category: str
    notes: str


class ActivityRepository:
    """Store local history and bookmarks in SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path("data/sqlbot_activity.sqlite")
        self._ensure_schema()

    def add_history(self, question: str, sql: str, is_success: bool) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO history (question, sql, timestamp, is_success)
                VALUES (?, ?, datetime('now', 'localtime'), ?)
                """,
                (question, sql, 1 if is_success else 0),
            )
            connection.execute(
                """
                DELETE FROM history
                WHERE id NOT IN (
                    SELECT id FROM history ORDER BY datetime(timestamp) DESC, id DESC LIMIT 100
                )
                """
            )

    def list_history(self, date_filter: str | None = None) -> list[HistoryEntry]:
        if date_filter:
            query = """
                SELECT id, question, sql, timestamp, is_success
                FROM history
                WHERE date(timestamp) = date(?)
                ORDER BY datetime(timestamp) DESC, id DESC
            """
            params: Iterable[object] = (date_filter,)
        else:
            query = """
                SELECT id, question, sql, timestamp, is_success
                FROM history
                ORDER BY datetime(timestamp) DESC, id DESC
                LIMIT 100
            """
            params = ()

        with self._connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [HistoryEntry(row[0], row[1], row[2], row[3], bool(row[4])) for row in rows]

    def add_bookmark(self, question: str, sql: str, category: str = "", notes: str = "") -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO bookmarks (question, sql, timestamp, category, notes)
                VALUES (?, ?, datetime('now', 'localtime'), ?, ?)
                """,
                (question, sql, category, notes),
            )

    def update_bookmark(self, bookmark_id: int, question: str, sql: str, category: str = "", notes: str = "") -> None:
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE bookmarks
                SET question = ?, sql = ?, category = ?, notes = ?
                WHERE id = ?
                """,
                (question, sql, category, notes, bookmark_id),
            )

    def list_bookmarks(self) -> list[BookmarkEntry]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, question, sql, timestamp, category, notes
                FROM bookmarks
                ORDER BY datetime(timestamp) DESC, id DESC
                """
            ).fetchall()
        return [BookmarkEntry(row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]

    def delete_bookmark(self, bookmark_id: int) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    sql TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_success INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    sql TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT ''
                )
                """
            )
