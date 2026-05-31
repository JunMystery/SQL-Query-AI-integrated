"""Evaluation helpers for Text-to-SQL quality checks."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Protocol

from sqlbot_desktop.infrastructure.database_manager import QueryExecutionResult
from sqlbot_desktop.services.query_validator import QueryValidator
from sqlbot_desktop.services.text_to_sql_pipeline import TextToSqlResult


class TextToSqlPipelineLike(Protocol):
    """Minimal pipeline interface used by the evaluator."""

    def generate(
        self,
        question: str,
        db_name: str,
        dialect: str,
        fallback_schema_context: str = "",
        execute_sql: Callable[[str], QueryExecutionResult] | None = None,
        max_retries: int = 3,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> TextToSqlResult:
        """Generate SQL for one evaluation case."""


@dataclass(frozen=True)
class EvaluationCase:
    """One Text-to-SQL evaluation item."""

    id: str
    question: str
    expected_sql: str = ""
    dialect: str = ""
    notes: str = ""


@dataclass(frozen=True)
class EvaluationItemResult:
    """Evaluation outcome for one case."""

    id: str
    question: str
    expected_sql: str
    generated_sql: str = ""
    exact_match: bool = False
    valid_select: bool = False
    execution_success: bool | None = None
    failure_type: str = ""
    message: str = ""
    selected_tables: list[str] = field(default_factory=list)
    selected_columns: list[str] = field(default_factory=list)
    attempts: int = 0


@dataclass(frozen=True)
class EvaluationMetrics:
    """Aggregate evaluation metrics."""

    total: int
    exact_match_rate: float
    valid_select_rate: float
    execution_success_rate: float | None
    schema_hallucination_rate: float


@dataclass(frozen=True)
class EvaluationReport:
    """Full evaluation report."""

    metrics: EvaluationMetrics
    results: list[EvaluationItemResult]

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": self.metrics.__dict__,
            "results": [result.__dict__ for result in self.results],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Text-to-SQL Evaluation Report",
            "",
            f"- Total: {self.metrics.total}",
            f"- Exact match: {self.metrics.exact_match_rate:.2%}",
            f"- Valid SELECT: {self.metrics.valid_select_rate:.2%}",
            f"- Schema hallucination: {self.metrics.schema_hallucination_rate:.2%}",
        ]
        if self.metrics.execution_success_rate is not None:
            lines.append(f"- Execution success: {self.metrics.execution_success_rate:.2%}")
        lines.extend(["", "## Failures"])
        failures = [result for result in self.results if result.failure_type]
        if not failures:
            lines.append("No failures.")
        for result in failures:
            lines.extend(
                [
                    f"- `{result.id}`: {result.failure_type}",
                    f"  - Question: {result.question}",
                    f"  - Message: {result.message}",
                    f"  - Selected tables: {', '.join(result.selected_tables) or '(none)'}",
                    f"  - Selected columns: {', '.join(result.selected_columns) or '(none)'}",
                ]
            )
        return "\n".join(lines)


class EvaluationDatasetLoader:
    """Load and validate JSON/CSV evaluation datasets."""

    REQUIRED_FIELDS = {"id", "question"}
    OPTIONAL_FIELDS = {"expected_sql", "dialect", "notes"}

    def load(self, path: Path) -> list[EvaluationCase]:
        suffix = path.suffix.lower()
        if suffix == ".json":
            return self._load_json(path)
        if suffix == ".csv":
            return self._load_csv(path)
        raise ValueError("Dataset must be .json or .csv")

    def _load_json(self, path: Path) -> list[EvaluationCase]:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        items = payload.get("cases", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ValueError("Dataset JSON must contain a list or a {'cases': [...]} object.")
        return self._items_to_cases(items)

    def _load_csv(self, path: Path) -> list[EvaluationCase]:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError("Dataset CSV must have a header row.")
            missing = self.REQUIRED_FIELDS - set(reader.fieldnames)
            if missing:
                raise ValueError(f"Dataset CSV is missing required fields: {', '.join(sorted(missing))}")
            return self._items_to_cases(list(reader))

    def _items_to_cases(self, items: Iterable[object]) -> list[EvaluationCase]:
        cases: list[EvaluationCase] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Dataset item #{index} must be an object.")
            missing = self.REQUIRED_FIELDS - set(item)
            if missing:
                raise ValueError(f"Dataset item #{index} is missing required fields: {', '.join(sorted(missing))}")
            case_id = str(item.get("id", "")).strip()
            question = str(item.get("question", "")).strip()
            if not case_id or not question:
                raise ValueError(f"Dataset item #{index} has empty id or question.")
            if case_id in seen_ids:
                raise ValueError(f"Duplicate dataset id: {case_id}")
            seen_ids.add(case_id)
            cases.append(
                EvaluationCase(
                    id=case_id,
                    question=question,
                    expected_sql=str(item.get("expected_sql", "")).strip(),
                    dialect=str(item.get("dialect", "")).strip(),
                    notes=str(item.get("notes", "")).strip(),
                )
            )
        return cases


class TextToSqlEvaluator:
    """Run pipeline outputs against a dataset and compute metrics."""

    def evaluate(
        self,
        cases: list[EvaluationCase],
        pipeline: TextToSqlPipelineLike,
        db_name: str,
        fallback_schema_context: str = "",
        execute_sql: Callable[[str], QueryExecutionResult] | None = None,
        default_dialect: str = "",
    ) -> EvaluationReport:
        results: list[EvaluationItemResult] = []
        for case in cases:
            result = pipeline.generate(
                case.question,
                db_name,
                case.dialect or default_dialect,
                fallback_schema_context,
                execute_sql=execute_sql,
            )
            generated_sql = result.queries[0] if result.queries else ""
            exact_match = bool(case.expected_sql) and normalize_sql(generated_sql) == normalize_sql(case.expected_sql)
            valid_select = QueryValidator.is_readonly_select(generated_sql) if generated_sql else False
            execution_success = result.execution_result.ok if result.execution_result is not None else None
            failure_type = FailureAnalyzer.classify(case, result, generated_sql, valid_select)
            results.append(
                EvaluationItemResult(
                    id=case.id,
                    question=case.question,
                    expected_sql=case.expected_sql,
                    generated_sql=generated_sql,
                    exact_match=exact_match,
                    valid_select=valid_select,
                    execution_success=execution_success,
                    failure_type=failure_type,
                    message=result.message,
                    selected_tables=result.diagnostics.selected_tables,
                    selected_columns=result.diagnostics.selected_columns,
                    attempts=result.diagnostics.attempts,
                )
            )
        return EvaluationReport(metrics=self._metrics(results), results=results)

    def _metrics(self, results: list[EvaluationItemResult]) -> EvaluationMetrics:
        total = len(results)
        if total == 0:
            return EvaluationMetrics(0, 0.0, 0.0, None, 0.0)
        execution_values = [result.execution_success for result in results if result.execution_success is not None]
        execution_rate = (
            sum(1 for value in execution_values if value) / len(execution_values)
            if execution_values
            else None
        )
        return EvaluationMetrics(
            total=total,
            exact_match_rate=sum(1 for result in results if result.exact_match) / total,
            valid_select_rate=sum(1 for result in results if result.valid_select) / total,
            execution_success_rate=execution_rate,
            schema_hallucination_rate=sum(1 for result in results if result.failure_type == "schema_hallucination") / total,
        )


class FailureAnalyzer:
    """Classify common Text-to-SQL failure modes."""

    UNKNOWN_SCHEMA_PATTERNS = (
        "unknown column",
        "no such column",
        "does not exist",
        "unknown table",
        "no such table",
    )

    @classmethod
    def classify(
        cls,
        case: EvaluationCase,
        result: TextToSqlResult,
        generated_sql: str,
        valid_select: bool,
    ) -> str:
        message = " ".join(
            [
                result.message,
                result.diagnostics.last_error,
                result.execution_result.message if result.execution_result else "",
            ]
        ).lower()
        if not generated_sql and not result.raw_text:
            return "empty_answer"
        if generated_sql and not valid_select:
            return "non_select"
        if any(pattern in message for pattern in cls.UNKNOWN_SCHEMA_PATTERNS):
            return "schema_hallucination"
        if result.execution_result and result.execution_result.error_type == "sql":
            return "sql_syntax"
        if not result.ok and not result.diagnostics.used_metadata:
            return "missing_schema_link"
        if case.expected_sql and generated_sql and normalize_sql(generated_sql) != normalize_sql(case.expected_sql):
            return "exact_mismatch"
        return ""


def normalize_sql(sql: str) -> str:
    cleaned = re.sub(r"--.*?$", " ", sql, flags=re.MULTILINE)
    cleaned = re.sub(r"/\*.*?\*/", " ", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip().rstrip(";")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.lower()
