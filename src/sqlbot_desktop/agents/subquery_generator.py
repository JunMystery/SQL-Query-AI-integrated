"""Subquery Generator module to detect subquery requirements and build subqueries."""

from __future__ import annotations


class SubqueryGenerator:
    """
    Detects queries requiring subqueries and constructs inner subqueries
    wrapped inside outer queries.
    """

    @classmethod
    def detect_subquery_need(cls, prompt: str) -> dict[str, str] | None:
        """
        Detects if the query needs a subquery from the natural language prompt.
        Returns a dict with 'pattern' and optional 'agg_func', or None.
        """
        prompt_lower = prompt.lower()

        # 1. Average / Aggregation comparison
        if any(kw in prompt_lower for kw in ["hơn trung bình", "lớn hơn trung bình", "cao hơn trung bình", "greater than average", "above average"]):
            return {"pattern": "scalar_compare", "agg_func": "AVG"}
        if any(kw in prompt_lower for kw in ["nhỏ hơn trung bình", "thấp hơn trung bình", "less than average", "below average"]):
            return {"pattern": "scalar_compare", "agg_func": "AVG"}

        # 2. Exists
        if any(kw in prompt_lower for kw in ["tồn tại", "có mặt trong", "exists"]):
            return {"pattern": "exists"}

        # 3. Not In / Exclude
        if any(kw in prompt_lower for kw in ["không có trong", "chưa từng", "không tồn tại", "not in", "not exists"]):
            return {"pattern": "not_in"}

        return None

    @classmethod
    def generate_subquery(
        cls,
        pattern: str,
        table: str,
        column: str,
        agg_func: str | None = None,
        where_clause: str | None = None
    ) -> str:
        """
        Constructs the inner subquery SQL string.
        """
        where = f" WHERE {where_clause}" if where_clause else ""
        pat = pattern.lower()
        if pat == "scalar_compare" and agg_func:
            return f"(SELECT {agg_func.upper()}({column}) FROM {table}{where})"
        elif pat == "exists":
            return f"EXISTS (SELECT 1 FROM {table}{where})"
        elif pat == "not_exists":
            return f"NOT EXISTS (SELECT 1 FROM {table}{where})"
        elif pat == "in":
            return f"(SELECT {column} FROM {table}{where})"
        elif pat == "not_in":
            return f"(SELECT {column} FROM {table}{where})"
        return ""

    @classmethod
    def wrap_query(
        cls,
        outer_select: str,
        outer_table: str,
        condition_column: str,
        operator: str,
        subquery_sql: str,
        outer_where_extra: str | None = None
    ) -> str:
        """
        Stitches the outer query and the subquery together.
        """
        where_parts = []
        op_upper = operator.upper()

        if op_upper in ("EXISTS", "NOT EXISTS"):
            where_parts.append(subquery_sql)
        else:
            where_parts.append(f"{condition_column} {operator} {subquery_sql}")

        if outer_where_extra:
            where_parts.append(outer_where_extra)

        where_clause = " AND ".join(where_parts)
        return f"SELECT {outer_select} FROM {outer_table} WHERE {where_clause}"
