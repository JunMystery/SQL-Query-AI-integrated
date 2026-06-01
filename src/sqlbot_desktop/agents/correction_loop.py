"""Correction Loop module to validate syntax, test execution, and correct SQL errors."""

from __future__ import annotations
from typing import Any
from sqlalchemy import text


class CorrectionLoop:
    """
    Validates SQL queries syntactically using sqlglot and executes them
    inside a test transaction that is rolled back immediately.
    Feeds errors back to the AI engine or fixer logic for up to 3 attempts.
    """

    def __init__(self, ai_engine: Any = None) -> None:
        self.ai_engine = ai_engine

    def validate_and_correct(
        self,
        query: str,
        dialect: str = "sqlite",
        db_connection: Any = None,
        max_attempts: int = 3,
        prompt_context: str | None = None
    ) -> str:
        """
        Validates the syntax and database execution of `query`.
        If errors are found, feeds them back to the LLM/ai_engine for up to max_attempts.
        """
        current_query = query.strip()
        dialect_mapped = self._map_dialect(dialect)
        sqlglot_parser = self._load_sqlglot()

        for attempt in range(max_attempts):
            error_msg = None

            # 1. Parse validation using sqlglot
            if sqlglot_parser is not None:
                try:
                    sqlglot_parser.parse_one(current_query, read=dialect_mapped)
                except Exception as e:
                    error_msg = f"SQL Syntax Error: {e}"

            # 2. Database validation if connection is provided and syntax is okay
            if not error_msg and db_connection is not None:
                try:
                    # Run in a rollback transaction
                    trans = db_connection.begin()
                    try:
                        db_connection.execute(text(current_query))
                    finally:
                        trans.rollback()
                except Exception as e:
                    error_msg = f"Database Execution Error: {e}"

            if not error_msg:
                # No errors, query is valid!
                return current_query

            # If we reached the last attempt or don't have an AI engine, return the last state
            if attempt == max_attempts - 1 or not self.ai_engine:
                break

            # Let's prompt the AI engine to fix the query
            current_query = self._call_ai_to_fix(current_query, error_msg, prompt_context)

        return current_query

    def _load_sqlglot(self) -> Any | None:
        try:
            import sqlglot
        except ImportError:
            return None
        return sqlglot

    def _map_dialect(self, dialect: str) -> str:
        d = dialect.lower().strip()
        if "postgres" in d:
            return "postgres"
        if "mysql" in d:
            return "mysql"
        if "sqlite" in d:
            return "sqlite"
        return d

    def _call_ai_to_fix(self, query: str, error_msg: str, prompt_context: str | None) -> str:
        system_prompt = (
            "You are a database SQL fixer. Fix the provided SQL query according to the syntax/execution error. "
            "Output only the corrected SQL query inside a ```sql ``` block, with no other text."
        )
        user_prompt = f"SQL Query:\n{query}\n\nError:\n{error_msg}\n\n"
        if prompt_context:
            user_prompt += f"Original prompt/context:\n{prompt_context}\n\n"
        user_prompt += "Please provide the corrected SQL."

        try:
            if getattr(self.ai_engine, "is_loaded", False):
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                raw_response = self.ai_engine.generate_chat_response(messages)
                from sqlbot_desktop.services.sql_extractor import SQLExtractor
                queries = SQLExtractor.extract_select_queries(raw_response)
                if queries:
                    return queries[0].strip()
                
                clean_lines = [l.strip() for l in raw_response.splitlines() if l.strip()]
                return clean_lines[0] if clean_lines else query
        except Exception:
            pass
        return query
