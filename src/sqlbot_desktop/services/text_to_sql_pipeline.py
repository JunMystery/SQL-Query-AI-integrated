"""Text-to-SQL orchestration pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Protocol

from sqlbot_desktop.infrastructure.database_manager import QueryExecutionResult
from sqlbot_desktop.infrastructure.few_shot_repository import FewShotRepository
from sqlbot_desktop.infrastructure.schema_metadata_repository import SchemaMetadataRepository
from sqlbot_desktop.models.entities import GenerationResult
from sqlbot_desktop.services.embedding_service import (
    DeterministicEmbeddingModel,
    EmbeddingModel,
    SentenceTransformersEmbeddingModel,
)
from sqlbot_desktop.services.prompt_builder import PromptBuilder
from sqlbot_desktop.services.query_logger import QueryAttempt, QueryLogger
from sqlbot_desktop.services.schema_linker import SchemaLinker
from sqlbot_desktop.services.schema_markdown_formatter import SchemaMarkdownFormatter
from sqlbot_desktop.services.sql_extractor import SQLExtractor


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


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
    error_history: list[str] = field(default_factory=list)


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
        query_logger: QueryLogger | None = None,
    ) -> None:
        self.ai_engine = ai_engine
        self.metadata_repository = metadata_repository or SchemaMetadataRepository()
        self.embedding_model = embedding_model or self._default_embedding_model()
        self.few_shot_repository = few_shot_repository or FewShotRepository()
        self.query_logger = query_logger

    def _default_embedding_model(self) -> EmbeddingModel:
        return SentenceTransformersEmbeddingModel(fallback_model=DeterministicEmbeddingModel())

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
        selected_examples = self.few_shot_repository.select_examples(question, dialect)
        few_shots = [example.to_prompt_dict() for example in selected_examples] if selected_examples else None
        attempts = max(1, max_retries)
        error_message = ""
        error_history: list[str] = []
        last_prompt = ""
        last_raw_text = ""
        last_queries: list[str] = []
        last_execution: QueryExecutionResult | None = None

        for attempt in range(1, attempts + 1):
            if check_cancelled and check_cancelled():
                error_message = "Thao tac bi huy"
                error_history.append(error_message)
                return TextToSqlResult(
                    False,
                    queries=last_queries,
                    message=error_message,
                    raw_text=last_raw_text,
                    prompt=last_prompt,
                    diagnostics=self._with_attempt(base_diagnostics, attempt, error_message, error_history),
                    execution_result=last_execution,
                )

            prompt = PromptBuilder.build(
                question,
                schema_context,
                dialect,
                error_message=error_message,
                few_shot_examples=few_shots,
                use_skeleton=True,
            )
            last_prompt = prompt
            diagnostics = self._with_attempt(base_diagnostics, attempt, error_message, error_history)
            logger.info("Text-to-SQL attempt %s/%s for db=%s dialect=%s", attempt, attempts, db_name, dialect)

            ai_result = self.ai_engine.generate_prompt(prompt, check_cancelled=check_cancelled)
            if not ai_result.ok:
                error_history.append(ai_result.message)
                self._log_attempt(question, attempt, "", ai_result.message, False)
                logger.warning("Text-to-SQL generation failed on attempt %s: %s", attempt, ai_result.message)
                return TextToSqlResult(
                    False,
                    message=ai_result.message,
                    prompt=prompt,
                    diagnostics=self._with_attempt(base_diagnostics, attempt, ai_result.message, error_history),
                    execution_result=last_execution,
                )

            last_raw_text = ai_result.message
            queries = ai_result.queries or SQLExtractor.extract_select_queries(last_raw_text)
            last_queries = queries
            if not queries:
                error_message = "AI khong tra ve cau SELECT hop le."
                error_history.append(error_message)
                self._log_attempt(question, attempt, "", error_message, False)
                logger.warning("Text-to-SQL attempt %s produced no safe SELECT", attempt)
                continue

            if execute_sql is None:
                self._log_attempt(question, attempt, queries[0] if queries else "", "", True)
                return TextToSqlResult(
                    True,
                    queries=queries,
                    message="Da sinh SQL. Chua kiem tra execution vi khong co database executor.",
                    raw_text=last_raw_text,
                    prompt=prompt,
                    diagnostics=diagnostics,
                )

            if check_cancelled and check_cancelled():
                error_message = "Thao tac bi huy"
                error_history.append(error_message)
                return TextToSqlResult(
                    False,
                    queries=last_queries,
                    message=error_message,
                    raw_text=last_raw_text,
                    prompt=prompt,
                    diagnostics=self._with_attempt(base_diagnostics, attempt, error_message, error_history),
                    execution_result=last_execution,
                )

            query = queries[0]
            execution = execute_sql(query)
            last_execution = execution
            if execution.ok:
                self._log_attempt(question, attempt, query, "", True)
                logger.info("Text-to-SQL execution succeeded on attempt %s", attempt)
                return TextToSqlResult(
                    True,
                    queries=[query],
                    message=f"Da sinh va kiem tra SQL sau {attempt} lan.",
                    raw_text=last_raw_text,
                    prompt=prompt,
                    diagnostics=diagnostics,
                    execution_result=execution,
                )

            error_message = execution.message or "SQL khong thuc thi duoc."
            error_history.append(error_message)
            self._log_attempt(question, attempt, query, error_message, False)
            logger.warning(
                "Text-to-SQL execution failed on attempt %s with type=%s: %s",
                attempt,
                execution.error_type,
                error_message,
            )

        return TextToSqlResult(
            False,
            queries=last_queries,
            message=error_message or "Khong the sinh SQL hop le.",
            raw_text=last_raw_text,
            prompt=last_prompt,
            diagnostics=self._with_attempt(base_diagnostics, attempts, error_message, error_history),
            execution_result=last_execution,
        )

    def _log_attempt(self, question: str, attempt: int, sql: str, error: str, success: bool) -> None:
        if self.query_logger is None:
            return
        try:
            self.query_logger.log_attempt(QueryAttempt(question, attempt, sql, error, success))
        except OSError as exc:
            logger.warning("Could not write query attempt log: %s", exc)

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
            message=link_result.message or "Dung schema context fallback.",
        )
        return fallback_schema_context, diagnostics

    def _with_attempt(
        self,
        diagnostics: TextToSqlDiagnostics,
        attempt: int,
        last_error: str = "",
        error_history: list[str] | None = None,
    ) -> TextToSqlDiagnostics:
        return TextToSqlDiagnostics(
            selected_tables=diagnostics.selected_tables,
            selected_columns=diagnostics.selected_columns,
            attempts=attempt,
            used_metadata=diagnostics.used_metadata,
            message=diagnostics.message,
            last_error=last_error,
            error_history=list(error_history or []),
        )
