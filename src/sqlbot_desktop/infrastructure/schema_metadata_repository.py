"""SQLite persistence for enriched schema metadata."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Iterator

from sqlbot_desktop.models.entities import ColumnMetadata


class SchemaMetadataRepository:
    """Store enriched schema metadata without modifying the source database."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path("data/schema_metadata.sqlite")
        self._ensure_schema()

    def upsert_column(self, metadata: ColumnMetadata) -> None:
        self.upsert_columns([metadata])

    def upsert_columns(self, rows: Iterable[ColumnMetadata]) -> None:
        with self._connection() as connection:
            connection.executemany(
                """
                INSERT INTO columns_metadata (
                    db_name,
                    table_name,
                    column_name,
                    data_type,
                    is_primary_key,
                    is_foreign_key,
                    referenced_table,
                    referenced_column,
                    business_description,
                    sample_values,
                    embedding
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(db_name, table_name, column_name)
                DO UPDATE SET
                    data_type = excluded.data_type,
                    is_primary_key = excluded.is_primary_key,
                    is_foreign_key = excluded.is_foreign_key,
                    referenced_table = excluded.referenced_table,
                    referenced_column = excluded.referenced_column,
                    business_description = CASE
                        WHEN excluded.business_description != '' THEN excluded.business_description
                        ELSE business_description
                    END,
                    sample_values = CASE
                        WHEN excluded.sample_values != '[]' THEN excluded.sample_values
                        ELSE sample_values
                    END,
                    embedding = COALESCE(excluded.embedding, embedding)
                """,
                [self._to_row(metadata) for metadata in rows],
            )

    def list_columns(self, db_name: str | None = None) -> list[ColumnMetadata]:
        if db_name:
            query = """
                SELECT db_name, table_name, column_name, data_type, is_primary_key, is_foreign_key,
                       referenced_table, referenced_column, business_description, sample_values, embedding
                FROM columns_metadata
                WHERE db_name = ?
                ORDER BY table_name, column_name
            """
            params: tuple[object, ...] = (db_name,)
        else:
            query = """
                SELECT db_name, table_name, column_name, data_type, is_primary_key, is_foreign_key,
                       referenced_table, referenced_column, business_description, sample_values, embedding
                FROM columns_metadata
                ORDER BY db_name, table_name, column_name
            """
            params = ()

        with self._connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._from_row(row) for row in rows]

    def get_column(self, db_name: str, table_name: str, column_name: str) -> ColumnMetadata | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT db_name, table_name, column_name, data_type, is_primary_key, is_foreign_key,
                       referenced_table, referenced_column, business_description, sample_values, embedding
                FROM columns_metadata
                WHERE db_name = ? AND table_name = ? AND column_name = ?
                """,
                (db_name, table_name, column_name),
            ).fetchone()
        return self._from_row(row) if row else None

    def search_columns(self, db_name: str, term: str) -> list[ColumnMetadata]:
        like_term = f"%{term.strip()}%"
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT db_name, table_name, column_name, data_type, is_primary_key, is_foreign_key,
                       referenced_table, referenced_column, business_description, sample_values, embedding
                FROM columns_metadata
                WHERE db_name = ?
                  AND (
                    table_name LIKE ?
                    OR column_name LIKE ?
                    OR business_description LIKE ?
                  )
                ORDER BY table_name, column_name
                """,
                (db_name, like_term, like_term, like_term),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update_business_description(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
        business_description: str,
    ) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE columns_metadata
                SET business_description = ?
                WHERE db_name = ? AND table_name = ? AND column_name = ?
                """,
                (business_description, db_name, table_name, column_name),
            )
            return cursor.rowcount > 0

    def update_sample_values(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
        sample_values: list[str],
    ) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE columns_metadata
                SET sample_values = ?
                WHERE db_name = ? AND table_name = ? AND column_name = ?
                """,
                (json.dumps(sample_values, ensure_ascii=False), db_name, table_name, column_name),
            )
            return cursor.rowcount > 0

    def update_embedding(
        self,
        db_name: str,
        table_name: str,
        column_name: str,
        embedding: bytes,
    ) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE columns_metadata
                SET embedding = ?
                WHERE db_name = ? AND table_name = ? AND column_name = ?
                """,
                (embedding, db_name, table_name, column_name),
            )
            return cursor.rowcount > 0

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
                CREATE TABLE IF NOT EXISTS columns_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    db_name TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    data_type TEXT NOT NULL DEFAULT '',
                    is_primary_key INTEGER NOT NULL DEFAULT 0,
                    is_foreign_key INTEGER NOT NULL DEFAULT 0,
                    referenced_table TEXT NOT NULL DEFAULT '',
                    referenced_column TEXT NOT NULL DEFAULT '',
                    business_description TEXT NOT NULL DEFAULT '',
                    sample_values TEXT NOT NULL DEFAULT '[]',
                    embedding BLOB,
                    UNIQUE(db_name, table_name, column_name)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_columns_metadata_lookup
                ON columns_metadata(db_name, table_name, column_name)
                """
            )

    def _to_row(self, metadata: ColumnMetadata) -> tuple[object, ...]:
        return (
            metadata.db_name,
            metadata.table_name,
            metadata.column_name,
            metadata.data_type,
            1 if metadata.is_primary_key else 0,
            1 if metadata.is_foreign_key else 0,
            metadata.referenced_table,
            metadata.referenced_column,
            metadata.business_description,
            json.dumps(metadata.sample_values, ensure_ascii=False),
            metadata.embedding,
        )

    def _from_row(self, row: sqlite3.Row | tuple[object, ...]) -> ColumnMetadata:
        sample_values = row[9]
        try:
            parsed_samples = json.loads(str(sample_values))
            samples = [str(value) for value in parsed_samples] if isinstance(parsed_samples, list) else []
        except json.JSONDecodeError:
            samples = []
        return ColumnMetadata(
            db_name=str(row[0]),
            table_name=str(row[1]),
            column_name=str(row[2]),
            data_type=str(row[3]),
            is_primary_key=bool(row[4]),
            is_foreign_key=bool(row[5]),
            referenced_table=str(row[6] or ""),
            referenced_column=str(row[7] or ""),
            business_description=str(row[8] or ""),
            sample_values=samples,
            embedding=row[10],
        )
