"""Tests for embedding-based schema linking."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.infrastructure.schema_metadata_repository import SchemaMetadataRepository  # noqa: E402
from sqlbot_desktop.models.entities import ColumnMetadata  # noqa: E402
from sqlbot_desktop.services.embedding_service import vector_to_blob  # noqa: E402
from sqlbot_desktop.services.schema_linker import SchemaLinker  # noqa: E402


class FixedEmbeddingModel:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed_text(self, text: str) -> list[float]:
        return self.vectors.get(text, [0.0, 0.0])


class SchemaLinkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repository = SchemaMetadataRepository(Path(self.temp_dir.name) / "metadata.sqlite")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_retrieve_relevant_columns_orders_by_cosine_similarity(self) -> None:
        self.repository.upsert_columns(
            [
                ColumnMetadata("demo", "users", "full_name", "TEXT", embedding=vector_to_blob([1.0, 0.0])),
                ColumnMetadata("demo", "orders", "total_amount", "DECIMAL", embedding=vector_to_blob([0.0, 1.0])),
            ]
        )
        linker = SchemaLinker(self.repository, FixedEmbeddingModel({"tên user": [1.0, 0.0]}))

        matches = linker.retrieve_relevant_columns("demo", "tên user", top_k=2)

        self.assertEqual(matches[0].column.table_name, "users")
        self.assertEqual(matches[0].column.column_name, "full_name")
        self.assertGreater(matches[0].score, matches[1].score)

    def test_link_schema_expands_to_referenced_table(self) -> None:
        self.repository.upsert_columns(
            [
                ColumnMetadata("demo", "orders", "user_id", "INTEGER", True, True, "users", "id", embedding=vector_to_blob([1.0, 0.0])),
                ColumnMetadata("demo", "orders", "status", "TEXT", embedding=vector_to_blob([0.8, 0.1])),
                ColumnMetadata("demo", "users", "id", "INTEGER", True, False, embedding=vector_to_blob([0.0, 1.0])),
                ColumnMetadata("demo", "users", "full_name", "TEXT", embedding=vector_to_blob([0.0, 0.8])),
            ]
        )
        linker = SchemaLinker(self.repository, FixedEmbeddingModel({"đơn hàng theo user": [1.0, 0.0]}))

        result = linker.link_schema("demo", "đơn hàng theo user", top_k=1, max_tables=5, max_columns=10)

        self.assertEqual(result.message, "")
        self.assertIn("orders", result.table_names)
        self.assertIn("users", result.table_names)
        self.assertTrue(any(column.table_name == "users" and column.column_name == "full_name" for column in result.columns))

    def test_link_schema_respects_limits(self) -> None:
        self.repository.upsert_columns(
            [
                ColumnMetadata("demo", "orders", "id", "INTEGER", embedding=vector_to_blob([1.0, 0.0])),
                ColumnMetadata("demo", "orders", "status", "TEXT", embedding=vector_to_blob([0.9, 0.0])),
                ColumnMetadata("demo", "users", "id", "INTEGER", embedding=vector_to_blob([0.8, 0.0])),
            ]
        )
        linker = SchemaLinker(self.repository, FixedEmbeddingModel({"orders": [1.0, 0.0]}))

        result = linker.link_schema("demo", "orders", top_k=3, max_tables=1, max_columns=2)

        self.assertLessEqual(len(result.table_names), 1)
        self.assertLessEqual(len(result.columns), 2)

    def test_keyword_fallback_when_embeddings_are_missing(self) -> None:
        self.repository.upsert_columns(
            [
                ColumnMetadata("demo", "users", "full_name", "TEXT", business_description="Tên người dùng"),
                ColumnMetadata("demo", "orders", "total_amount", "DECIMAL"),
            ]
        )
        linker = SchemaLinker(self.repository, FixedEmbeddingModel({"Tên người dùng": [1.0, 0.0]}))

        result = linker.link_schema("demo", "Tên người dùng", top_k=2)

        self.assertIn("keyword fallback", result.message)
        self.assertEqual(result.columns[0].table_name, "users")
        self.assertEqual(result.columns[0].column_name, "full_name")

    def test_empty_metadata_returns_clear_message(self) -> None:
        linker = SchemaLinker(self.repository, FixedEmbeddingModel({"anything": [1.0, 0.0]}))

        result = linker.link_schema("demo", "anything")

        self.assertEqual(result.columns, [])
        self.assertIn("chưa có dữ liệu", result.message)


if __name__ == "__main__":
    unittest.main()
