"""Tests for schema metadata import and enrichment services."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.infrastructure.schema_metadata_repository import SchemaMetadataRepository  # noqa: E402
from sqlbot_desktop.models.entities import ColumnInfo, TableInfo  # noqa: E402
from sqlbot_desktop.services.embedding_service import blob_to_vector, vector_to_blob  # noqa: E402
from sqlbot_desktop.services.schema_metadata_service import SchemaMetadataService  # noqa: E402


class FixedEmbeddingModel:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector
        self.calls: list[str] = []

    def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        return self.vector


class SchemaMetadataServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.repository = SchemaMetadataRepository(self.base_path / "metadata.sqlite")
        self.service = SchemaMetadataService(self.repository)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_import_tables_maps_columns_and_foreign_keys(self) -> None:
        tables = [
            TableInfo("users", [ColumnInfo("id", "INTEGER", is_primary=True)]),
            TableInfo(
                "orders",
                [
                    ColumnInfo("id", "INTEGER", is_primary=True),
                    ColumnInfo("user_id", "INTEGER", is_foreign=True),
                    ColumnInfo("status", "TEXT"),
                ],
                foreign_keys=[
                    {
                        "constrained_table": "orders",
                        "constrained_column": "user_id",
                        "referred_table": "users",
                        "referred_column": "id",
                    }
                ],
            ),
        ]

        imported = self.service.import_tables("demo", tables)

        self.assertEqual(imported, 4)
        fk_column = self.repository.get_column("demo", "orders", "user_id")
        self.assertIsNotNone(fk_column)
        assert fk_column is not None
        self.assertTrue(fk_column.is_foreign_key)
        self.assertEqual(fk_column.referenced_table, "users")
        self.assertEqual(fk_column.referenced_column, "id")

    def test_import_tables_preserves_raw_sample_values(self) -> None:
        imported = self.service.import_tables(
            "demo",
            [
                TableInfo(
                    "users",
                    [
                        ColumnInfo(
                            "status",
                            "TEXT",
                            sample_value="active",
                            enum_values=["active", "locked", "pending", "archived"],
                        )
                    ],
                )
            ],
        )

        row = self.repository.get_column("demo", "users", "status")

        self.assertEqual(imported, 1)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.sample_values, ["active", "locked", "pending"])

    def test_import_business_descriptions_updates_only_matching_columns(self) -> None:
        self.service.import_tables("demo", [TableInfo("users", [ColumnInfo("status", "TEXT")])])
        path = self.base_path / "descriptions.json"
        path.write_text(
            json.dumps(
                {
                    "columns": [
                        {
                            "db_name": "demo",
                            "table_name": "users",
                            "column_name": "status",
                            "business_description": "Trạng thái tài khoản",
                        },
                        {
                            "db_name": "other",
                            "table_name": "users",
                            "column_name": "status",
                            "business_description": "Bỏ qua",
                        },
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        updated = self.service.import_business_descriptions("demo", path)

        self.assertEqual(updated, 1)
        row = self.repository.get_column("demo", "users", "status")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.business_description, "Trạng thái tài khoản")

    def test_export_business_description_template(self) -> None:
        self.service.import_tables("demo", [TableInfo("users", [ColumnInfo("name", "TEXT")])])
        self.repository.update_business_description("demo", "users", "name", "Tên hiển thị")
        path = self.base_path / "export" / "descriptions.json"

        exported = self.service.export_business_description_template("demo", path)

        payload = json.loads(exported.read_text(encoding="utf-8"))
        self.assertEqual(payload["columns"][0]["table_name"], "users")
        self.assertEqual(payload["columns"][0]["business_description"], "Tên hiển thị")

    def test_refresh_sample_values_uses_safe_selects_and_skips_sensitive_columns(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        with engine.connect() as connection:
            connection.execute(text("CREATE TABLE users (id INTEGER, name TEXT, password_hash TEXT)"))
            connection.execute(text("INSERT INTO users VALUES (1, 'Lan', 'secret')"))
            connection.execute(text("INSERT INTO users VALUES (2, 'Minh', 'secret2')"))
            connection.execute(text("INSERT INTO users VALUES (3, 'Lan', 'secret3')"))
            connection.execute(text("INSERT INTO users VALUES (4, 'Tu', 'secret4')"))
            connection.execute(text("INSERT INTO users VALUES (5, 'Hoa', 'secret5')"))
            connection.commit()

            self.service.import_tables(
                "demo",
                [
                    TableInfo(
                        "users",
                        [
                            ColumnInfo("id", "INTEGER"),
                            ColumnInfo("name", "TEXT"),
                            ColumnInfo("password_hash", "TEXT"),
                        ],
                    )
                ],
            )

            messages = self.service.refresh_sample_values("demo", connection, limit=3)

        self.assertEqual(messages, [])
        name = self.repository.get_column("demo", "users", "name")
        password = self.repository.get_column("demo", "users", "password_hash")
        self.assertIsNotNone(name)
        self.assertIsNotNone(password)
        assert name is not None
        assert password is not None
        self.assertEqual(name.sample_values, ["Lan", "Minh", "Tu"])
        self.assertEqual(password.sample_values, ["[REDACTED]"])

    def test_refresh_sample_values_collects_per_column_errors(self) -> None:
        engine = create_engine("sqlite:///:memory:", future=True)
        with engine.connect() as connection:
            self.service.import_tables("demo", [TableInfo("missing_table", [ColumnInfo("name", "TEXT")])])

            messages = self.service.refresh_sample_values("demo", connection, limit=3)

        self.assertEqual(len(messages), 1)
        self.assertIn("missing_table.name", messages[0])

    def test_refresh_embeddings_updates_missing_rows_only_by_default(self) -> None:
        self.service.import_tables(
            "demo",
            [
                TableInfo(
                    "users",
                    [
                        ColumnInfo("name", "TEXT"),
                        ColumnInfo("status", "TEXT"),
                    ],
                )
            ],
        )
        self.repository.update_embedding("demo", "users", "status", vector_to_blob([9.0, 9.0]))
        model = FixedEmbeddingModel([1.0, 0.0])

        updated = self.service.refresh_embeddings("demo", model)

        self.assertEqual(updated, 1)
        self.assertEqual(len(model.calls), 1)
        name = self.repository.get_column("demo", "users", "name")
        status = self.repository.get_column("demo", "users", "status")
        self.assertIsNotNone(name)
        self.assertIsNotNone(status)
        assert name is not None
        assert status is not None
        self.assertEqual(blob_to_vector(name.embedding), [1.0, 0.0])
        self.assertEqual(blob_to_vector(status.embedding), [9.0, 9.0])

    def test_refresh_embeddings_force_updates_existing_rows(self) -> None:
        self.service.import_tables("demo", [TableInfo("users", [ColumnInfo("name", "TEXT")])])
        self.repository.update_embedding("demo", "users", "name", vector_to_blob([9.0, 9.0]))
        model = FixedEmbeddingModel([0.0, 1.0])

        updated = self.service.refresh_embeddings("demo", model, force=True)

        self.assertEqual(updated, 1)
        row = self.repository.get_column("demo", "users", "name")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(blob_to_vector(row.embedding), [0.0, 1.0])


if __name__ == "__main__":
    unittest.main()
