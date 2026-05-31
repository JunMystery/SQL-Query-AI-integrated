"""Set Operation Handler module to detect and stitch set-operation SQL queries."""

from __future__ import annotations
import re


class SetOpHandler:
    """
    Detects set operations (UNION, UNION ALL, INTERSECT, EXCEPT) from natural language prompts,
    and stitches individual queries using the operator.
    """

    OP_KEYWORDS = {
        "UNION ALL": ["kết hợp tất cả", "gộp cả trùng", "union all"],
        "UNION": ["kết hợp", "gộp", "hợp", "union"],
        "INTERSECT": ["giao", "vừa thuộc", "vừa có", "intersect"],
        "EXCEPT": ["ngoại trừ", "nhưng không", "hiệu", "except"],
    }

    @classmethod
    def detect_set_op(cls, prompt: str) -> str | None:
        """
        Detects set operations from natural language prompts.
        Prioritizes UNION ALL over UNION since UNION ALL is a longer match.
        """
        prompt_lower = prompt.lower()
        for op in ["UNION ALL", "UNION", "INTERSECT", "EXCEPT"]:
            keywords = cls.OP_KEYWORDS[op]
            if any(kw in prompt_lower for kw in keywords):
                return op
        return None

    @classmethod
    def stitch_queries(cls, queries: list[str], operator: str) -> str:
        """
        Stitches independent SQL queries with the specified set operator.
        Strips trailing semicolons from individual queries first.
        """
        clean_queries = []
        for q in queries:
            q_strip = q.strip()
            if q_strip.endswith(";"):
                q_strip = q_strip[:-1].strip()
            clean_queries.append(q_strip)

        op_str = f" {operator.upper()} "
        return op_str.join(clean_queries)
