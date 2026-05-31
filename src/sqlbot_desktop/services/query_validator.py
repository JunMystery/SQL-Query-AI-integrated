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
        tokens = set(re.findall(r"[a-z_]+", normalized))
        return not bool(tokens & cls.DANGEROUS_KEYWORDS)

    @classmethod
    def filter_readonly(cls, queries: list[str]) -> list[str]:
        return [query for query in queries if cls.is_readonly_select(query)]

    @classmethod
    def _strip_leading_comments(cls, sql: str) -> str:
        cleaned = sql.lstrip()
        while cleaned.startswith("--"):
            _, separator, remainder = cleaned.partition("\n")
            if not separator:
                return ""
            cleaned = remainder.lstrip()
        return cleaned
