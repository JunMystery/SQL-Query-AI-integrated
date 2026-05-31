"""Embedding-based schema linking for text-to-SQL."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from sqlbot_desktop.infrastructure.schema_metadata_repository import SchemaMetadataRepository
from sqlbot_desktop.models.entities import ColumnMetadata
from sqlbot_desktop.services.embedding_service import (
    EmbeddingModel,
    blob_to_vector,
    cosine_similarity,
)


@dataclass(frozen=True)
class ColumnMatch:
    """A metadata column with its schema-linking score."""

    column: ColumnMetadata
    score: float


@dataclass(frozen=True)
class SchemaLinkResult:
    """Subset schema selected for a user question."""

    columns: list[ColumnMetadata] = field(default_factory=list)
    matches: list[ColumnMatch] = field(default_factory=list)
    message: str = ""

    @property
    def table_names(self) -> list[str]:
        seen: set[str] = set()
        names: list[str] = []
        for column in self.columns:
            if column.table_name not in seen:
                seen.add(column.table_name)
                names.append(column.table_name)
        return names


class SchemaLinker:
    """Retrieve relevant metadata columns and expand them through foreign keys."""

    def __init__(
        self,
        repository: SchemaMetadataRepository,
        embedding_model: EmbeddingModel,
    ) -> None:
        self.repository = repository
        self.embedding_model = embedding_model

    def retrieve_relevant_columns(self, db_name: str, question: str, top_k: int = 20) -> list[ColumnMatch]:
        question_vector = self.embedding_model.embed_text(question)
        matches: list[ColumnMatch] = []
        for metadata in self.repository.list_columns(db_name):
            column_vector = blob_to_vector(metadata.embedding)
            if not column_vector:
                continue
            score = cosine_similarity(question_vector, column_vector)
            matches.append(ColumnMatch(metadata, score))
        matches.sort(key=lambda match: match.score, reverse=True)
        return matches[: max(1, top_k)]

    def link_schema(
        self,
        db_name: str,
        question: str,
        top_k: int = 20,
        max_tables: int = 15,
        max_columns: int = 50,
    ) -> SchemaLinkResult:
        all_columns = self.repository.list_columns(db_name)
        if not all_columns:
            return SchemaLinkResult(message="Schema metadata chưa có dữ liệu.")

        matches = [match for match in self.retrieve_relevant_columns(db_name, question, top_k) if match.score > 0]
        if not matches:
            fallback_columns = self._keyword_fallback(all_columns, question, max_columns)
            return SchemaLinkResult(
                columns=fallback_columns,
                matches=[],
                message="Schema metadata chưa có embedding; đã dùng keyword fallback.",
            )

        selected = self.expand_with_foreign_keys(
            db_name,
            [match.column for match in matches],
            max_tables=max_tables,
            max_columns=max_columns,
        )
        return SchemaLinkResult(columns=selected, matches=matches)

    def expand_with_foreign_keys(
        self,
        db_name: str,
        selected_columns: list[ColumnMetadata],
        max_tables: int = 15,
        max_columns: int = 50,
    ) -> list[ColumnMetadata]:
        all_columns = self.repository.list_columns(db_name)
        table_order: list[str] = []

        def add_table(table_name: str) -> None:
            if table_name and table_name not in table_order and len(table_order) < max_tables:
                table_order.append(table_name)

        for metadata in selected_columns:
            add_table(metadata.table_name)
            if metadata.is_foreign_key and metadata.referenced_table:
                add_table(metadata.referenced_table)

        selected_tables = set(table_order)
        for metadata in all_columns:
            if metadata.table_name in selected_tables and metadata.is_foreign_key and metadata.referenced_table:
                add_table(metadata.referenced_table)
            if metadata.referenced_table in selected_tables:
                add_table(metadata.table_name)
            selected_tables = set(table_order)
            if len(table_order) >= max_tables:
                break

        selected_tables = set(table_order)
        subset: list[ColumnMetadata] = []
        added_keys: set[tuple[str, str]] = set()

        for metadata in selected_columns:
            key = (metadata.table_name, metadata.column_name)
            if key in added_keys:
                continue
            if len(subset) >= max_columns:
                break
            subset.append(metadata)
            added_keys.add(key)

        for metadata in all_columns:
            key = (metadata.table_name, metadata.column_name)
            if metadata.table_name in selected_tables and key not in added_keys:
                if len(subset) >= max_columns:
                    break
                subset.append(metadata)
                added_keys.add(key)

        return subset

    def _keyword_fallback(
        self,
        all_columns: list[ColumnMetadata],
        question: str,
        max_columns: int,
    ) -> list[ColumnMetadata]:
        keywords = set(re.findall(r"[\w]+", question.lower(), flags=re.UNICODE))
        scored: list[tuple[int, ColumnMetadata]] = []
        for metadata in all_columns:
            haystack = " ".join(
                [
                    metadata.table_name,
                    metadata.column_name,
                    metadata.data_type,
                    metadata.business_description,
                    " ".join(metadata.sample_values),
                ]
            ).lower()
            score = sum(1 for keyword in keywords if keyword and keyword in haystack)
            if score:
                scored.append((score, metadata))
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored:
            return [metadata for _, metadata in scored[:max_columns]]
        return all_columns[:max_columns]
