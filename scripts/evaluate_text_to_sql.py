"""Evaluate Text-to-SQL dataset files in dry-run mode.

This script intentionally does not open a production database by default.
It validates the dataset format and can produce a baseline report using
expected_sql as the generated SQL, which is useful for checking report output.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.services.evaluation import EvaluationDatasetLoader, TextToSqlEvaluator  # noqa: E402
from sqlbot_desktop.services.text_to_sql_pipeline import TextToSqlResult  # noqa: E402


class ExpectedSqlPipeline:
    """Dry-run baseline that emits expected_sql for each case by question."""

    def __init__(self, expected_by_question: dict[str, str]) -> None:
        self.expected_by_question = expected_by_question

    def generate(self, question: str, db_name: str, dialect: str, fallback_schema_context: str = "", **kwargs):
        sql = self.expected_by_question.get(question, "")
        if not sql:
            return TextToSqlResult(False, message="No expected_sql baseline available.")
        return TextToSqlResult(True, queries=[sql], message="Dry-run baseline.", raw_text=sql)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Evaluate Text-to-SQL datasets.")
    parser.add_argument("dataset", type=Path, help="JSON or CSV dataset path.")
    parser.add_argument("--output", type=Path, help="Optional report output path.")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--db-name", default="evaluation")
    args = parser.parse_args()

    cases = EvaluationDatasetLoader().load(args.dataset)
    pipeline = ExpectedSqlPipeline({case.question: case.expected_sql for case in cases})
    report = TextToSqlEvaluator().evaluate(cases, pipeline, db_name=args.db_name)
    content = report.to_json() if args.format == "json" else report.to_markdown()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
