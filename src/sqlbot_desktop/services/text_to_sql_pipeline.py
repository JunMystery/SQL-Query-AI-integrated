"""Text-to-SQL orchestration pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from sqlbot_desktop.infrastructure.database_manager import QueryExecutionResult
from sqlbot_desktop.infrastructure.few_shot_repository import FewShotRepository
from sqlbot_desktop.infrastructure.schema_metadata_repository import SchemaMetadataRepository
from sqlbot_desktop.models.entities import GenerationResult
from sqlbot_desktop.services.embedding_service import DeterministicEmbeddingModel, EmbeddingModel
from sqlbot_desktop.services.prompt_builder import PromptBuilder
from sqlbot_desktop.services.schema_linker import SchemaLinker
from sqlbot_desktop.services.schema_markdown_formatter import SchemaMarkdownFormatter
from sqlbot_desktop.services.sql_extractor import SQLExtractor


class PromptGeneratingAI(Protocol):
    """Minimal AI interface needed by the pipeline."""

    def generate_prompt(
        self,
        prompt: str,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> GenerationResult:
        """Generate SQL from a fully built prompt."""


@dataclass(frozen=True)
class TextToSqlDiagnostics:
    """Diagnostic metadata for a generation attempt."""

    selected_tables: list[str] = field(default_factory=list)
    selected_columns: list[str] = field(default_factory=list)
    attempts: int = 1
    used_metadata: bool = False
    message: str = ""
    last_error: str = ""


@dataclass(frozen=True)
class TextToSqlResult:
    """Pipeline generation result."""

    ok: bool
    queries: list[str] = field(default_factory=list)
    message: str = ""
    raw_text: str = ""
    prompt: str = ""
    diagnostics: TextToSqlDiagnostics = field(default_factory=TextToSqlDiagnostics)
    execution_result: QueryExecutionResult | None = None


class TextToSqlPipeline:
    """Build prompt context, call AI, extract safe SELECT candidates."""

    def __init__(
        self,
        ai_engine: PromptGeneratingAI,
        metadata_repository: SchemaMetadataRepository | None = None,
        embedding_model: EmbeddingModel | None = None,
        few_shot_repository: FewShotRepository | None = None,
    ) -> None:
        self.ai_engine = ai_engine
        self.metadata_repository = metadata_repository or SchemaMetadataRepository()
        self.embedding_model = embedding_model or DeterministicEmbeddingModel()
        self.few_shot_repository = few_shot_repository or FewShotRepository()

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
        schema_context, base_diagnostics = self._schema_context(db_name, question, fallback_schema_context)
        few_shots = [example.to_prompt_dict() for example in self.few_shot_repository.select_examples(question, dialect)]
        attempts = max(1, max_retries)
        error_message = ""
        last_prompt = ""
        last_raw_text = ""
        last_queries: list[str] = []
        last_execution: QueryExecutionResult | None = None

        for attempt in range(1, attempts + 1):
            prompt = PromptBuilder.build(
                question,
                schema_context,
                dialect,
                error_message=error_message,
                few_shot_examples=few_shots,
            )
            last_prompt = prompt
            diagnostics = self._with_attempt(base_diagnostics, attempt, error_message)
            ai_result = self.ai_engine.generate_prompt(prompt, check_cancelled=check_cancelled)
            if not ai_result.ok:
                return TextToSqlResult(False, message=ai_result.message, prompt=prompt, diagnostics=diagnostics)

            last_raw_text = ai_result.message
            queries = ai_result.queries or SQLExtractor.extract_select_queries(last_raw_text)
            last_queries = queries
            if not queries:
                error_message = "AI không trả về câu SELECT hợp lệ."
                continue

            if execute_sql is None:
                return TextToSqlResult(
                    True,
                    queries=queries,
                    message="Đã sinh SQL.",
                    raw_text=last_raw_text,
                    prompt=prompt,
                    diagnostics=diagnostics,
                )

            query = queries[0]
            execution = execute_sql(query)
            last_execution = execution
            if execution.ok:
                return TextToSqlResult(
                    True,
                    queries=[query],
                    message=f"Đã sinh và kiểm tra SQL sau {attempt} lần.",
                    raw_text=last_raw_text,
                    prompt=prompt,
                    diagnostics=diagnostics,
                    execution_result=execution,
                )
            error_message = execution.message or "SQL không thực thi được."

        return TextToSqlResult(
            False,
            queries=last_queries,
            message=error_message or "Không thể sinh SQL hợp lệ.",
            raw_text=last_raw_text,
            prompt=last_prompt,
            diagnostics=self._with_attempt(base_diagnostics, attempts, error_message),
            execution_result=last_execution,
        )

    def _schema_context(
        self,
        db_name: str,
        question: str,
        fallback_schema_context: str,
    ) -> tuple[str, TextToSqlDiagnostics]:
        linker = SchemaLinker(self.metadata_repository, self.embedding_model)
        link_result = linker.link_schema(db_name, question, top_k=20, max_tables=15, max_columns=50)
        if link_result.columns:
            schema_context = SchemaMarkdownFormatter.format(link_result.columns)
            diagnostics = TextToSqlDiagnostics(
                selected_tables=link_result.table_names,
                selected_columns=[f"{column.table_name}.{column.column_name}" for column in link_result.columns],
                used_metadata=not bool(link_result.message),
                message=link_result.message,
            )
            return schema_context, diagnostics

        diagnostics = TextToSqlDiagnostics(
            used_metadata=False,
            message=link_result.message or "Dùng schema context fallback.",
        )
        return fallback_schema_context, diagnostics

    def _with_attempt(
        self,
        diagnostics: TextToSqlDiagnostics,
        attempt: int,
        last_error: str = "",
    ) -> TextToSqlDiagnostics:
        return TextToSqlDiagnostics(
            selected_tables=diagnostics.selected_tables,
            selected_columns=diagnostics.selected_columns,
            attempts=attempt,
            used_metadata=diagnostics.used_metadata,
            message=diagnostics.message,
            last_error=last_error,
        )
