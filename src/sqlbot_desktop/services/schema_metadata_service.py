"""Application service for building and enriching schema metadata."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import column, select, table
from sqlalchemy.engine import Connection
from sqlalchemy.sql import quoted_name

from sqlbot_desktop.infrastructure.schema_extractor import SchemaExtractor
from sqlbot_desktop.infrastructure.schema_metadata_repository import SchemaMetadataRepository
from sqlbot_desktop.models.entities import ColumnMetadata, TableInfo
from sqlbot_desktop.services.embedding_service import EmbeddingModel, vector_to_blob


class SchemaMetadataService:
    """Build metadata in a local SQLite store without changing the source database."""

    SENSITIVE_MARKERS = ("pass", "token", "secret", "key", "phone", "email", "avatar", "auth", "hash")
    LARGE_TYPE_MARKERS = ("blob", "binary", "bytea", "image", "json", "xml")

    def __init__(self, repository: SchemaMetadataRepository | None = None) -> None:
        self.repository = repository or SchemaMetadataRepository()

    def import_from_connection(self, db_name: str, connection: Connection) -> int:
        tables = SchemaExtractor(connection).get_all_tables_columns()
        return self.import_tables(db_name, tables)

    def import_tables(self, db_name: str, tables: list[TableInfo]) -> int:
        rows: list[ColumnMetadata] = []
        for table_info in tables:
            foreign_key_map = self._foreign_key_map(table_info)
            for column_info in table_info.columns:
                referenced_table, referenced_column = foreign_key_map.get(column_info.name, ("", ""))
                rows.append(
                    ColumnMetadata(
                        db_name=db_name,
                        table_name=table_info.name,
                        column_name=column_info.name,
                        data_type=column_info.type_name,
                        is_primary_key=column_info.is_primary,
                        is_foreign_key=column_info.is_foreign or bool(referenced_table),
                        referenced_table=referenced_table,
                        referenced_column=referenced_column,
                        sample_values=self._column_sample_values(column_info),
                    )
                )
        self.repository.upsert_columns(rows)
        return len(rows)

    def import_business_descriptions(self, db_name: str, path: Path) -> int:
        payload = self._load_json(path)
        updated = 0
        for item in self._description_items(payload):
            table_name = str(item.get("table_name", "")).strip()
            column_name = str(item.get("column_name", "")).strip()
            description = str(item.get("business_description", "")).strip()
            item_db_name = str(item.get("db_name", db_name)).strip() or db_name
            if item_db_name != db_name or not table_name or not column_name:
                continue
            if self.repository.update_business_description(db_name, table_name, column_name, description):
                updated += 1
        return updated

    def export_business_description_template(self, db_name: str, path: Path) -> Path:
        rows = self.repository.list_columns(db_name)
        payload = {
            "columns": [
                {
                    "db_name": row.db_name,
                    "table_name": row.table_name,
                    "column_name": row.column_name,
                    "business_description": row.business_description,
                }
                for row in rows
            ]
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return path

    def refresh_sample_values(
        self,
        db_name: str,
        connection: Connection,
        limit: int = 3,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> list[str]:
        messages: list[str] = []
        grouped_columns: dict[str, list[ColumnMetadata]] = {}
        for metadata in self.repository.list_columns(db_name):
            if check_cancelled and check_cancelled():
                return messages
            if self._should_skip_samples(metadata):
                self.repository.update_sample_values(
                    db_name,
                    metadata.table_name,
                    metadata.column_name,
                    ["[REDACTED]"] if self._is_sensitive(metadata.column_name) else [],
                )
                continue

            grouped_columns.setdefault(metadata.table_name, []).append(metadata)

        for table_name, columns in grouped_columns.items():
            if check_cancelled and check_cancelled():
                break
            try:
                table_samples = self._fetch_table_sample_values(
                    connection,
                    table_name,
                    [metadata.column_name for metadata in columns],
                    limit,
                )
            except Exception as exc:
                for metadata in columns:
                    messages.append(f"{metadata.table_name}.{metadata.column_name}: {exc}")
                continue

            for metadata in columns:
                if check_cancelled and check_cancelled():
                    return messages
                samples = table_samples.get(metadata.column_name, [])
                self.repository.update_sample_values(db_name, metadata.table_name, metadata.column_name, samples)
        return messages

    def refresh_embeddings(
        self,
        db_name: str,
        embedding_model: EmbeddingModel,
        force: bool = False,
        check_cancelled: Any | None = None,
    ) -> int:
        updated = 0
        for metadata in self.repository.list_columns(db_name):
            if check_cancelled and check_cancelled():
                break
            if metadata.embedding and not force:
                continue
            vector = embedding_model.embed_text(self._embedding_text(metadata))
            if self.repository.update_embedding(
                db_name,
                metadata.table_name,
                metadata.column_name,
                vector_to_blob(vector),
            ):
                updated += 1
        return updated

    def _fetch_sample_values(
        self,
        connection: Connection,
        table_name: str,
        column_name: str,
        limit: int,
    ) -> list[str]:
        table_ref = table(quoted_name(table_name, True), column(quoted_name(column_name, True)))
        column_ref = next(iter(table_ref.c))
        statement = (
            select(column_ref)
            .select_from(table_ref)
            .where(column_ref.is_not(None))
            .distinct()
            .limit(max(1, limit))
        )
        values = connection.execute(statement).fetchall()
        return [self._clip_sample(row[0]) for row in values if row[0] is not None]

    def _fetch_table_sample_values(
        self,
        connection: Connection,
        table_name: str,
        column_names: list[str],
        limit: int,
    ) -> dict[str, list[str]]:
        if not column_names:
            return {}
        unique_names = list(dict.fromkeys(column_names))
        column_refs = [column(quoted_name(column_name, True)) for column_name in unique_names]
        table_ref = table(quoted_name(table_name, True), *column_refs)
        scan_limit = max(1, min(max(limit * 20, limit), 200))
        statement = select(*table_ref.c).select_from(table_ref).limit(scan_limit)
        rows = connection.execute(statement).fetchall()
        samples = {column_name: [] for column_name in unique_names}
        for row in rows:
            for index, column_name in enumerate(unique_names):
                if len(samples[column_name]) >= limit:
                    continue
                value = row[index]
                if value is None:
                    continue
                sample = self._clip_sample(value)
                if sample and sample not in samples[column_name]:
                    samples[column_name].append(sample)
        return samples

    def _foreign_key_map(self, table_info: TableInfo) -> dict[str, tuple[str, str]]:
        mapping: dict[str, tuple[str, str]] = {}
        for foreign_key in table_info.foreign_keys:
            constrained_column = str(foreign_key.get("constrained_column", ""))
            referred_table = str(foreign_key.get("referred_table", ""))
            referred_column = str(foreign_key.get("referred_column", ""))
            if constrained_column:
                mapping[constrained_column] = (referred_table, referred_column)
        return mapping

    def _column_sample_values(self, column_info: object) -> list[str]:
        samples: list[str] = []
        sample_value = str(getattr(column_info, "sample_value", "") or "").strip()
        if sample_value:
            samples.append(sample_value)
        for value in getattr(column_info, "enum_values", []) or []:
            sample = str(value).strip()
            if sample and sample not in samples:
                samples.append(sample)
            if len(samples) >= 3:
                break
        return samples[:3]

    def _description_items(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(payload.get("columns"), list):
            return [item for item in payload["columns"] if isinstance(item, dict)]

        tables = payload.get("tables", {})
        if not isinstance(tables, dict):
            return []

        items: list[dict[str, Any]] = []
        for table_name, table_payload in tables.items():
            if not isinstance(table_payload, dict):
                continue
            column_payloads = table_payload.get("columns", {})
            if not isinstance(column_payloads, dict):
                continue
            for column_name, column_payload in column_payloads.items():
                if not isinstance(column_payload, dict):
                    continue
                items.append(
                    {
                        "table_name": table_name,
                        "column_name": column_name,
                        "business_description": column_payload.get("business_description")
                        or column_payload.get("description")
                        or "",
                    }
                )
        return items

    def _load_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise ValueError("Business description file must contain a JSON object.")
        return payload

    def _should_skip_samples(self, metadata: ColumnMetadata) -> bool:
        data_type = metadata.data_type.lower()
        return self._is_sensitive(metadata.column_name) or any(marker in data_type for marker in self.LARGE_TYPE_MARKERS)

    def _is_sensitive(self, column_name: str) -> bool:
        normalized = column_name.lower()
        return any(marker in normalized for marker in self.SENSITIVE_MARKERS)

    def _clip_sample(self, value: object) -> str:
        sample = str(value)
        return sample if len(sample) <= 80 else f"{sample[:77]}..."

    def _embedding_text(self, metadata: ColumnMetadata) -> str:
        samples = ", ".join(metadata.sample_values)
        return " ".join(
            part
            for part in [
                metadata.table_name,
                metadata.column_name,
                metadata.data_type,
                metadata.business_description,
                samples,
            ]
            if part
        )
