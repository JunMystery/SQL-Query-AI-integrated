"""Grouping Handler module to automatically append GROUP BY columns and split HAVING conditions."""

from __future__ import annotations
import re


class GroupingHandler:
    """
    Parses SELECT columns to find non-aggregated fields for GROUP BY,
    and splits filter conditions into WHERE vs HAVING.
    """

    AGGREGATE_PATTERN = re.compile(r"\b(SUM|AVG|COUNT|MAX|MIN)\b", re.IGNORECASE)

    @classmethod
    def is_aggregate(cls, expression: str) -> bool:
        """Returns True if the expression contains an aggregate function."""
        return bool(cls.AGGREGATE_PATTERN.search(expression))

    @classmethod
    def parse_group_by(cls, select_columns: list[str]) -> list[str]:
        """
        Parses select columns to find non-aggregated columns.
        If there is at least one aggregate column, returns all non-aggregate column names/expressions.
        Otherwise, returns empty list.
        """
        has_aggregate = any(cls.is_aggregate(col) for col in select_columns)
        if not has_aggregate:
            return []

        group_by_cols = []
        for col in select_columns:
            if not cls.is_aggregate(col):
                # Clean up alias if exists (e.g. "user_id AS uid" -> "user_id")
                # Split by case-insensitive "AS"
                base_col = re.split(r"\s+AS\s+", col, flags=re.IGNORECASE)[0].strip()
                group_by_cols.append(base_col)

        return group_by_cols

    @classmethod
    def formulate_having(cls, filters: list[str]) -> tuple[list[str], list[str]]:
        """
        Splits a list of filter conditions into WHERE conditions (non-aggregate)
        and HAVING conditions (aggregate).
        """
        where_conditions = []
        having_conditions = []

        for f in filters:
            if cls.is_aggregate(f):
                having_conditions.append(f)
            else:
                where_conditions.append(f)

        return where_conditions, having_conditions
