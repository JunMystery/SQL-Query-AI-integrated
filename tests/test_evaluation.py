"""Tests for Text-to-SQL evaluation dataset and reporting."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.infrastructure.database_manager import QueryExecutionResult  # noqa: E402
from sqlbot_desktop.services.evaluation import (  # noqa: E402
    EvaluationCase,
    EvaluationDatasetLoader,
    FailureAnalyzer,
    TextToSqlEvaluator,
    normalize_sql,
)
from sqlbot_desktop.services.text_to_sql_pipeline import TextToSqlDiagnostics, TextToSqlResult  # noqa: E402


class FakePipeline:
    def __init__(self, results: dict[str, TextToSqlResult]) -> None:
        self.results = results
        self.calls: list[str] = []

    def generate(self, question: str, db_name: str, dialect: str, fallback_schema_context: str = "", **kwargs):
        self.calls.append(question)
        return self.results[question]


class EvaluationDatasetLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_loads_json_dataset(self) -> None:
        path = self.base_path / "dataset.json"
        path.write_text(
            json.dumps(
                {
                    "cases": [
                        {
                            "id": "case_1",
                            "question": "Liệt kê user",
                            "expected_sql": "SELECT * FROM users;",
                            "dialect": "MYSQL",
                            "notes": "demo",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        cases = EvaluationDatasetLoader().load(path)

        self.assertEqual(cases, [EvaluationCase("case_1", "Liệt kê user", "SELECT * FROM users;", "MYSQL", "demo")])

    def test_loads_csv_dataset(self) -> None:
        path = self.base_path / "dataset.csv"
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["id", "question", "expected_sql", "dialect", "notes"])
            writer.writeheader()
            writer.writerow(
                {
                    "id": "case_1",
                    "question": "Liệt kê user",
                    "expected_sql": "SELECT * FROM users;",
                    "dialect": "POSTGRESQL",
                    "notes": "demo",
                }
            )

        cases = EvaluationDatasetLoader().load(path)

        self.assertEqual(cases[0].dialect, "POSTGRESQL")
        self.assertEqual(cases[0].question, "Liệt kê user")

    def test_rejects_missing_required_fields_and_duplicate_ids(self) -> None:
        missing_path = self.base_path / "missing.json"
        missing_path.write_text(json.dumps([{"id": "case_1"}]), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "question"):
            EvaluationDatasetLoader().load(missing_path)

        duplicate_path = self.base_path / "duplicate.json"
        duplicate_path.write_text(
            json.dumps([{"id": "case_1", "question": "A"}, {"id": "case_1", "question": "B"}]),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            EvaluationDatasetLoader().load(duplicate_path)

    def test_sample_dataset_loads(self) -> None:
        cases = EvaluationDatasetLoader().load(PROJECT_ROOT / "docs" / "evaluation_dataset_sample.json")

        self.assertGreaterEqual(len(cases), 5)
        self.assertTrue(all(case.id and case.question for case in cases))
        ids = {case.id for case in cases}
        self.assertTrue(
            {
                "simple_select_001",
                "filter_status_001",
                "join_001",
                "aggregate_001",
                "group_by_001",
                "order_by_001",
                "date_filter_001",
            }.issubset(ids)
        )
        self.assertTrue(all(case.expected_sql.upper().startswith("SELECT") for case in cases))

    def test_sample_dataset_dry_run_baseline_is_exact_match(self) -> None:
        cases = EvaluationDatasetLoader().load(PROJECT_ROOT / "docs" / "evaluation_dataset_sample.json")

        class ExpectedSqlPipeline:
            def generate(self, question: str, db_name: str, dialect: str, fallback_schema_context: str = "", **kwargs):
                for case in cases:
                    if case.question == question:
                        return TextToSqlResult(True, queries=[case.expected_sql], message="baseline", raw_text=case.expected_sql)
                return TextToSqlResult(False, message="missing baseline")

        report = TextToSqlEvaluator().evaluate(cases, ExpectedSqlPipeline(), db_name="demo")

        self.assertEqual(report.metrics.exact_match_rate, 1.0)
        self.assertEqual(report.metrics.valid_select_rate, 1.0)


class TextToSqlEvaluatorTests(unittest.TestCase):
    def test_evaluate_dry_run_metrics_and_markdown(self) -> None:
        cases = [
            EvaluationCase("case_1", "A", "SELECT id FROM users;", "MYSQL"),
            EvaluationCase("case_2", "B", "SELECT total FROM orders;", "MYSQL"),
        ]
        pipeline = FakePipeline(
            {
                "A": TextToSqlResult(
                    True,
                    queries=["SELECT id FROM users;"],
                    message="ok",
                    diagnostics=TextToSqlDiagnostics(selected_tables=["users"], selected_columns=["users.id"], used_metadata=True),
                ),
                "B": TextToSqlResult(
                    True,
                    queries=["SELECT amount FROM orders;"],
                    message="ok",
                    diagnostics=TextToSqlDiagnostics(selected_tables=["orders"], selected_columns=["orders.amount"], used_metadata=True),
                ),
            }
        )

        report = TextToSqlEvaluator().evaluate(cases, pipeline, db_name="demo")

        self.assertEqual(report.metrics.total, 2)
        self.assertEqual(report.metrics.exact_match_rate, 0.5)
        self.assertEqual(report.metrics.valid_select_rate, 1.0)
        self.assertIsNone(report.metrics.execution_success_rate)
        self.assertEqual(report.results[1].failure_type, "exact_mismatch")
        self.assertIn("Exact match", report.to_markdown())
        self.assertIn("case_2", report.to_json())

    def test_evaluate_with_execution_success_metrics(self) -> None:
        cases = [EvaluationCase("case_1", "A", "SELECT id FROM users;", "MYSQL")]
        pipeline = FakePipeline(
            {
                "A": TextToSqlResult(
                    True,
                    queries=["SELECT id FROM users;"],
                    message="ok",
                    execution_result=QueryExecutionResult(True, "ok", ["id"], [[1]], row_count=1),
                )
            }
        )

        report = TextToSqlEvaluator().evaluate(cases, pipeline, db_name="demo")

        self.assertEqual(report.metrics.execution_success_rate, 1.0)

    def test_failure_analyzer_classifies_common_failures(self) -> None:
        case = EvaluationCase("case_1", "A", "SELECT id FROM users;")

        self.assertEqual(
            FailureAnalyzer.classify(case, TextToSqlResult(False, message=""), "", False),
            "empty_answer",
        )
        self.assertEqual(
            FailureAnalyzer.classify(case, TextToSqlResult(True, queries=["DELETE FROM users;"]), "DELETE FROM users;", False),
            "non_select",
        )
        self.assertEqual(
            FailureAnalyzer.classify(
                case,
                TextToSqlResult(
                    False,
                    message="column user_name does not exist",
                    execution_result=QueryExecutionResult(False, "column user_name does not exist", error_type="sql"),
                ),
                "SELECT user_name FROM users;",
                True,
            ),
            "schema_hallucination",
        )

    def test_normalize_sql_ignores_case_whitespace_and_semicolon(self) -> None:
        self.assertEqual(
            normalize_sql("SELECT  id\nFROM users;"),
            normalize_sql("select id from users"),
        )


if __name__ == "__main__":
    unittest.main()
