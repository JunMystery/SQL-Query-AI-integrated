"""SQL safety validation."""

from __future__ import annotations

import re


class QueryValidator:
    """Allow only read-only SELECT statements."""

    DANGEROUS_KEYWORDS = {
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "create",
        "truncate",
        "exec",
        "execute",
        "merge",
        "grant",
        "revoke",
    }

    @classmethod
    def is_readonly_select(cls, sql: str) -> bool:
        normalized = cls._strip_leading_comments(sql).strip().lower()
        if not normalized.startswith("select"):
            return False
        if cls._has_multiple_statements(normalized):
            return False
        tokens = set(re.findall(r"[a-z_]+", normalized))
        return not bool(tokens & cls.DANGEROUS_KEYWORDS)

    @classmethod
    def filter_readonly(cls, queries: list[str]) -> list[str]:
        return [query for query in queries if cls.is_readonly_select(query)]

    @classmethod
    def _strip_leading_comments(cls, sql: str) -> str:
        cleaned = sql.lstrip()
        while True:
            if cleaned.startswith("--"):
                _, separator, remainder = cleaned.partition("\n")
                if not separator:
                    return ""
                cleaned = remainder.lstrip()
                continue
            if cleaned.startswith("/*"):
                _, separator, remainder = cleaned.partition("*/")
                if not separator:
                    return ""
                cleaned = remainder.lstrip()
                continue
            return cleaned

    @classmethod
    def _has_multiple_statements(cls, sql: str) -> bool:
        in_single_quote = False
        in_double_quote = False
        first_statement_ended = False
        index = 0
        while index < len(sql):
            char = sql[index]
            next_char = sql[index + 1] if index + 1 < len(sql) else ""

            if not in_single_quote and not in_double_quote and char == "-" and next_char == "-":
                newline = sql.find("\n", index + 2)
                if newline == -1:
                    break
                index = newline + 1
                continue

            if not in_single_quote and not in_double_quote and char == "/" and next_char == "*":
                end = sql.find("*/", index + 2)
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
                first_statement_ended = True
            elif first_statement_ended and not char.isspace():
                return True
            index += 1
        return False
