"""Extract safe SELECT statements from LLM output."""

from __future__ import annotations

import re

from sqlbot_desktop.services.query_validator import QueryValidator


class SQLExtractor:
    """Extract valid SELECT statements while rejecting prose and unsafe SQL."""

    FENCE_PATTERN = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)

    @classmethod
    def extract_select_queries(cls, raw_text: str, limit: int = 3) -> list[str]:
        candidates = cls._candidate_blocks(raw_text)
        queries: list[str] = []
        for candidate in candidates:
            candidate_for_validation = candidate if candidate.rstrip().endswith(";") else f"{candidate};"
            if not QueryValidator.is_readonly_select(candidate_for_validation):
                continue
            statement = cls._first_statement(candidate)
            if not statement:
                continue
            if not statement.endswith(";"):
                statement = f"{statement};"
            if QueryValidator.is_readonly_select(statement):
                queries.append(statement)
            if len(queries) >= limit:
                break
        return queries

    @classmethod
    def _candidate_blocks(cls, raw_text: str) -> list[str]:
        fenced = [match.strip() for match in cls.FENCE_PATTERN.findall(raw_text) if match.strip()]
        if fenced:
            return fenced
        cleaned = raw_text.strip()
        if QueryValidator._strip_leading_comments(cleaned).strip().lower().startswith("select"):
            return [cleaned]
        return []

    @classmethod
    def _first_statement(cls, text: str) -> str:
        in_single_quote = False
        in_double_quote = False
        index = 0
        while index < len(text):
            char = text[index]
            next_char = text[index + 1] if index + 1 < len(text) else ""
            if not in_single_quote and not in_double_quote and char == "-" and next_char == "-":
                newline = text.find("\n", index + 2)
                if newline == -1:
                    break
                index = newline + 1
                continue
            if not in_single_quote and not in_double_quote and char == "/" and next_char == "*":
                end = text.find("*/", index + 2)
                if end == -1:
                    break
                index = end + 2
                continue
            if char == "'" and not in_double_quote:
                if in_single_quote and next_char == "'":
                    index += 2
                    continue
                in_single_quote = not in_single_quote
            elif char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif char == ";" and not in_single_quote and not in_double_quote:
                return text[: index + 1].strip()
            index += 1
        return text.strip()
