"""SQL safety validation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _SqlScanResult:
    valid: bool
    has_comment: bool = False
    has_multiple_statements: bool = False
    sql_without_string_literals: str = ""


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
        normalized = cls._strip_leading_comments(sql).strip()
        if not normalized.lower().startswith("select"):
            return False
        scan = cls._scan_sql(normalized)
        if not scan.valid or scan.has_comment or scan.has_multiple_statements:
            return False
        tokens = set(re.findall(r"[a-z_]+", scan.sql_without_string_literals.lower()))
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
    def _scan_sql(cls, sql: str) -> _SqlScanResult:
        cleaned: list[str] = []
        in_single_quote = False
        in_double_quote = False
        first_statement_ended = False
        index = 0
        while index < len(sql):
            char = sql[index]
            next_char = sql[index + 1] if index + 1 < len(sql) else ""

            if not in_single_quote and not in_double_quote and char == "-" and next_char == "-":
                return _SqlScanResult(False, has_comment=True)

            if not in_single_quote and not in_double_quote and char == "/" and next_char == "*":
                return _SqlScanResult(False, has_comment=True)

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
                return _SqlScanResult(False, has_multiple_statements=True)
            elif not in_single_quote and not in_double_quote:
                cleaned.append(char)
            index += 1
        if in_single_quote or in_double_quote:
            return _SqlScanResult(False)
        return _SqlScanResult(True, sql_without_string_literals="".join(cleaned))
