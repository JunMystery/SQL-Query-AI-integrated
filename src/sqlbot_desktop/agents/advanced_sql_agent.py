"""Advanced SQL Agent module linking natural language questions, structured JSON intent parsing, and SQL orchestration."""

from __future__ import annotations
import json
from typing import Any
from sqlbot_desktop.models.entities import TableInfo, ColumnMetadata
from sqlbot_desktop.agents.orchestrator import Orchestrator


class AdvancedSQLAgent:
    """
    Combines intent extraction, join planning, aggregation grouping, and validation.
    Falls back gracefully to traditional prompt-builder based generation if intent parsing fails.
    """

    def __init__(self, ai_engine: Any, metadata_list: list[Any] | None = None) -> None:
        self.ai_engine = ai_engine
        self.metadata_list = metadata_list or []

    def generate_sql(self, user_input: str, db_connection: Any = None, dialect: str = "sqlite") -> str:
        """
        Generates a syntactically correct and validated SQL query for user_input.
        Utilizes database schema metadata and self-corrects via CorrectionLoop.
        """
        # 1. Resolve metadata list from DB connection or fallbacks
        metadata = list(self.metadata_list)
        if db_connection is not None:
            try:
                from sqlbot_desktop.infrastructure.schema_extractor import SchemaExtractor
                extractor = SchemaExtractor(db_connection)
                extracted = extractor.get_all_tables_columns()
                if extracted:
                    metadata = extracted
            except Exception:
                pass

        if not metadata:
            try:
                from sqlbot_desktop.infrastructure.schema_metadata_repository import SchemaMetadataRepository
                repo = SchemaMetadataRepository()
                metadata = repo.list_columns()
            except Exception:
                pass

        # 2. Call the AI engine to parse input into a structured JSON query plan
        if self.ai_engine and getattr(self.ai_engine, "is_loaded", False):
            try:
                system_prompt = (
                    "You are a SQL query planner. Analyze the user's natural language request and "
                    "output a JSON object specifying the start_table, target_tables, select_columns, "
                    "and filter_expression. Output ONLY the JSON object, nothing else.\n"
                    "Example format:\n"
                    "{\n"
                    "  \"start_table\": \"users\",\n"
                    "  \"target_tables\": [\"orders\"],\n"
                    "  \"select_columns\": [\"id\", \"name\", \"SUM(orders.amount) AS total\"],\n"
                    "  \"filter_expression\": \"SUM(orders.amount) > 100\"\n"
                    "}"
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Request: {user_input}"}
                ]
                raw_response = self.ai_engine.generate_chat_response(messages)

                # Clean up markdown code blocks if wrapped around the JSON response
                clean_json = raw_response.strip()
                if clean_json.startswith("```"):
                    start_idx = clean_json.find("{")
                    end_idx = clean_json.rfind("}")
                    if start_idx != -1 and end_idx != -1:
                        clean_json = clean_json[start_idx:end_idx + 1]

                data = json.loads(clean_json)
                start_table = data.get("start_table")
                target_tables = data.get("target_tables", [])
                select_columns = data.get("select_columns", [])
                filter_expression = data.get("filter_expression")

                if start_table and select_columns:
                    orchestrator = Orchestrator(
                        metadata_list=metadata,
                        ai_engine=self.ai_engine,
                        db_connection=db_connection,
                        dialect=dialect
                    )
                    return orchestrator.orchestrate(
                        question=user_input,
                        start_table=start_table,
                        target_tables=target_tables,
                        select_columns=select_columns,
                        filter_expression=filter_expression
                    )
            except Exception:
                # Fall back to traditional text-to-SQL generation path on failure
                pass

        # 3. Traditional text-to-SQL prompt builder fallback route
        if self.ai_engine:
            schema_context = ""
            if metadata:
                try:
                    from sqlbot_desktop.services.schema_rag import SchemaRAG
                    if isinstance(metadata[0], TableInfo):
                        schema_context = SchemaRAG.get_rag_schema_context(user_input, metadata)
                    else:
                        from sqlbot_desktop.services.schema_markdown_formatter import SchemaMarkdownFormatter
                        schema_context = SchemaMarkdownFormatter.format(metadata)
                except Exception:
                    pass

            gen_res = self.ai_engine.generate(user_input, schema_context=schema_context, dialect=dialect)
            if gen_res.ok and gen_res.queries:
                return gen_res.queries[0]

        return ""
