"""Tests for the TextToSqlPipeline orchestration service."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.infrastructure.database_manager import QueryExecutionResult  # noqa: E402
from sqlbot_desktop.infrastructure.few_shot_repository import FewShotRepository  # noqa: E402
from sqlbot_desktop.infrastructure.schema_metadata_repository import SchemaMetadataRepository  # noqa: E402
from sqlbot_desktop.models.entities import ColumnMetadata, GenerationResult  # noqa: E402
from sqlbot_desktop.services.embedding_service import vector_to_blob  # noqa: E402
from sqlbot_desktop.services.text_to_sql_pipeline import TextToSqlPipeline  # noqa: E402


class FixedEmbeddingModel:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed_text(self, text: str) -> list[float]:
        return self.vectors.get(text, [1.0, 0.0])


class FakeAIEngine:
    def __init__(self, result: GenerationResult | list[GenerationResult]) -> None:
        self.results = result if isinstance(result, list) else [result]
        self.prompts: list[str] = []

    def generate_prompt(self, prompt: str, check_cancelled=None) -> GenerationResult:
        self.prompts.append(prompt)
        index = min(len(self.prompts) - 1, len(self.results) - 1)
        return self.results[index]


class TextToSqlPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.metadata = SchemaMetadataRepository(self.base_path / "metadata.sqlite")
        self.few_shots = FewShotRepository(self.base_path / "few_shot.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_pipeline_uses_linked_schema_and_extracts_safe_sql(self) -> None:
        self.metadata.upsert_columns(
            [
                ColumnMetadata("demo", "users", "full_name", "TEXT", embedding=vector_to_blob([1.0, 0.0])),
                ColumnMetadata("demo", "orders", "total", "DECIMAL", embedding=vector_to_blob([0.0, 1.0])),
            ]
        )
        ai = FakeAIEngine(GenerationResult(True, message="```sql\nSELECT full_name FROM users;\n```"))
        pipeline = TextToSqlPipeline(
            ai,
            self.metadata,
            FixedEmbeddingModel({"Tên user": [1.0, 0.0]}),
            self.few_shots,
        )

        result = pipeline.generate("Tên user", "demo", "MYSQL", "fallback schema")

        self.assertTrue(result.ok)
        self.assertEqual(result.queries, ["SELECT full_name FROM users;"])
        self.assertTrue(result.diagnostics.used_metadata)
        self.assertEqual(result.diagnostics.selected_tables, ["users"])
        self.assertIn("## Table: users", ai.prompts[0])
        self.assertNotIn("fallback schema", ai.prompts[0])

    def test_pipeline_defaults_to_neural_embedding_with_deterministic_fallback(self) -> None:
        ai = FakeAIEngine(GenerationResult(True, message="SELECT * FROM fallback_table;"))
        pipeline = TextToSqlPipeline(ai, self.metadata, few_shot_repository=self.few_shots)

        self.assertEqual(type(pipeline.embedding_model).__name__, "SentenceTransformersEmbeddingModel")
        self.assertEqual(type(pipeline.embedding_model.fallback_model).__name__, "DeterministicEmbeddingModel")

    def test_pipeline_falls_back_when_metadata_is_empty(self) -> None:
        ai = FakeAIEngine(GenerationResult(True, message="SELECT * FROM fallback_table;"))
        pipeline = TextToSqlPipeline(ai, self.metadata, FixedEmbeddingModel({}), self.few_shots)

        result = pipeline.generate("anything", "demo", "POSTGRESQL", "TABLE fallback_table")

        self.assertTrue(result.ok)
        self.assertFalse(result.diagnostics.used_metadata)
        self.assertIn("chưa có dữ liệu", result.diagnostics.message)
        self.assertIn("TABLE fallback_table", ai.prompts[0])
        self.assertIn("SQL planning process", ai.prompts[0])
        self.assertIn("Đếm số đơn hàng theo trạng thái", ai.prompts[0])

    def test_pipeline_returns_failure_when_ai_has_no_valid_select(self) -> None:
        ai = FakeAIEngine(GenerationResult(True, message="Tôi không biết."))
        pipeline = TextToSqlPipeline(ai, self.metadata, FixedEmbeddingModel({}), self.few_shots)

        result = pipeline.generate("anything", "demo", "MYSQL", "TABLE users")

        self.assertFalse(result.ok)
        self.assertIn("SELECT", result.message)

    def test_pipeline_propagates_ai_failure(self) -> None:
        ai = FakeAIEngine(GenerationResult(False, message="Chưa load AI backend."))
        pipeline = TextToSqlPipeline(ai, self.metadata, FixedEmbeddingModel({}), self.few_shots)

        result = pipeline.generate("anything", "demo", "MYSQL", "TABLE users")

        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Chưa load AI backend.")

    def test_pipeline_retries_sql_execution_error_and_succeeds(self) -> None:
        ai = FakeAIEngine(
            [
                GenerationResult(True, message="```sql\nSELECT missing_column FROM users;\n```"),
                GenerationResult(True, message="```sql\nSELECT full_name FROM users;\n```"),
            ]
        )
        executions: list[str] = []

        def execute_sql(sql: str) -> QueryExecutionResult:
            executions.append(sql)
            if "missing_column" in sql:
                return QueryExecutionResult(False, "column missing_column does not exist", error_type="sql", sql=sql)
            return QueryExecutionResult(True, "ok", ["full_name"], [["Lan"]], row_count=1, sql=sql)

        pipeline = TextToSqlPipeline(ai, self.metadata, FixedEmbeddingModel({}), self.few_shots)

        result = pipeline.generate("Tên user", "demo", "MYSQL", "TABLE users", execute_sql=execute_sql)

        self.assertTrue(result.ok)
        self.assertEqual(result.queries, ["SELECT full_name FROM users;"])
        self.assertEqual(result.diagnostics.attempts, 2)
        self.assertEqual(executions, ["SELECT missing_column FROM users;", "SELECT full_name FROM users;"])
        self.assertIn("PREVIOUS SQL ERROR", ai.prompts[1])
        self.assertIn("missing_column", ai.prompts[1])
        self.assertEqual(result.diagnostics.error_history, ["column missing_column does not exist"])

    def test_pipeline_retries_when_ai_returns_non_select(self) -> None:
        ai = FakeAIEngine(
            [
                GenerationResult(True, message="```sql\nDELETE FROM users;\n```"),
                GenerationResult(True, message="```sql\nSELECT id FROM users;\n```"),
            ]
        )
        pipeline = TextToSqlPipeline(ai, self.metadata, FixedEmbeddingModel({}), self.few_shots)

        result = pipeline.generate(
            "Lấy user",
            "demo",
            "MYSQL",
            "TABLE users",
            execute_sql=lambda sql: QueryExecutionResult(True, "ok", ["id"], [[1]], row_count=1, sql=sql),
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.diagnostics.attempts, 2)
        self.assertIn("AI khong tra ve cau SELECT hop le", ai.prompts[1])

    def test_pipeline_returns_last_error_after_max_retries(self) -> None:
        ai = FakeAIEngine(GenerationResult(True, message="```sql\nSELECT missing_column FROM users;\n```"))
        pipeline = TextToSqlPipeline(ai, self.metadata, FixedEmbeddingModel({}), self.few_shots)

        result = pipeline.generate(
            "Tên user",
            "demo",
            "MYSQL",
            "TABLE users",
            execute_sql=lambda sql: QueryExecutionResult(False, "column missing_column does not exist", error_type="sql", sql=sql),
            max_retries=2,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.diagnostics.attempts, 2)
        self.assertIn("missing_column", result.message)
        self.assertEqual(
            result.diagnostics.error_history,
            ["column missing_column does not exist", "column missing_column does not exist"],
        )
        self.assertEqual(len(ai.prompts), 2)

    def test_pipeline_stops_before_execution_when_cancelled_after_generation(self) -> None:
        ai = FakeAIEngine(GenerationResult(True, message="```sql\nSELECT id FROM users;\n```"))
        pipeline = TextToSqlPipeline(ai, self.metadata, FixedEmbeddingModel({}), self.few_shots)
        calls = {"count": 0}
        executed: list[str] = []

        def check_cancelled() -> bool:
            calls["count"] += 1
            return calls["count"] >= 2

        result = pipeline.generate(
            "Lay user",
            "demo",
            "MYSQL",
            "TABLE users",
            execute_sql=lambda sql: executed.append(sql) or QueryExecutionResult(True),
            check_cancelled=check_cancelled,
        )

        self.assertFalse(result.ok)
        self.assertEqual(executed, [])
        self.assertIn("huy", result.message)
        self.assertEqual(result.diagnostics.error_history, ["Thao tac bi huy"])


if __name__ == "__main__":
    unittest.main()
