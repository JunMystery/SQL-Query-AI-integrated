"""Tests for local schema metadata persistence."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.infrastructure.schema_metadata_repository import SchemaMetadataRepository  # noqa: E402
from sqlbot_desktop.models.entities import ColumnMetadata  # noqa: E402


class SchemaMetadataRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "schema_metadata.sqlite"
        self.repository = SchemaMetadataRepository(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_upsert_and_list_columns(self) -> None:
        self.repository.upsert_column(
            ColumnMetadata(
                db_name="demo",
                table_name="users",
                column_name="id",
                data_type="INTEGER",
                is_primary_key=True,
                sample_values=["1", "2"],
                embedding=b"abc",
            )
        )

        rows = self.repository.list_columns("demo")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].table_name, "users")
        self.assertTrue(rows[0].is_primary_key)
        self.assertEqual(rows[0].sample_values, ["1", "2"])
        self.assertEqual(rows[0].embedding, b"abc")

    def test_upsert_preserves_enrichment_when_schema_is_refreshed(self) -> None:
        self.repository.upsert_column(
            ColumnMetadata(
                db_name="demo",
                table_name="users",
                column_name="name",
                data_type="VARCHAR",
                business_description="Tên người dùng",
                sample_values=["Lan"],
                embedding=b"vector",
            )
        )

        self.repository.upsert_column(
            ColumnMetadata(
                db_name="demo",
                table_name="users",
                column_name="name",
                data_type="TEXT",
            )
        )

        row = self.repository.get_column("demo", "users", "name")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.data_type, "TEXT")
        self.assertEqual(row.business_description, "Tên người dùng")
        self.assertEqual(row.sample_values, ["Lan"])
        self.assertEqual(row.embedding, b"vector")

    def test_search_columns_matches_table_column_or_description(self) -> None:
        self.repository.upsert_columns(
            [
                ColumnMetadata("demo", "users", "full_name", "TEXT", business_description="Tên đầy đủ"),
                ColumnMetadata("demo", "orders", "total_amount", "DECIMAL"),
            ]
        )

        matches = self.repository.search_columns("demo", "Tên")

        self.assertEqual([row.column_name for row in matches], ["full_name"])

    def test_update_business_description_and_sample_values(self) -> None:
        self.repository.upsert_column(ColumnMetadata("demo", "users", "status", "TEXT"))

        self.assertTrue(
            self.repository.update_business_description("demo", "users", "status", "Trạng thái tài khoản")
        )
        self.assertTrue(self.repository.update_sample_values("demo", "users", "status", ["active", "locked"]))

        row = self.repository.get_column("demo", "users", "status")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.business_description, "Trạng thái tài khoản")
        self.assertEqual(row.sample_values, ["active", "locked"])


if __name__ == "__main__":
    unittest.main()
