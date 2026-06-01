"""Operator Classifier and Parser for advanced SQL operators in query text."""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Union, List, Optional


@dataclass
class ConditionNode:
    """Represents a single query condition (e.g. age BETWEEN 18 AND 30)."""
    column: str
    operator: str  # BETWEEN, IN, LIKE, EXISTS, IS NULL, IS NOT NULL, etc.
    values: list[str]


@dataclass
class LogicalNode:
    """Represents a logical combination (AND, OR) of condition or logical nodes."""
    connector: str  # AND, OR
    children: list[Union[LogicalNode, ConditionNode]]


class OperatorClassifier:
    """
    Identifies advanced query operators from query text and parses
    conditional expressions into logical trees of AND/OR relationships.
    """

    # Keyword mappings for natural language classification
    NL_KEYWORDS = {
        "BETWEEN": ["between", "nằm trong khoảng", "từ", "khoảng giữa"],
        "IN": ["in", "trong danh sách", "trong số", "thuộc"],
        "LIKE": ["like", "chứa", "bắt đầu bằng", "kết thúc bằng", "tương tự"],
        "EXISTS": ["exists", "tồn tại", "có mặt"],
        "IS NULL": ["is null", "rỗng", "chưa nhập", "không có giá trị"],
        "IS NOT NULL": ["is not null", "không rỗng", "đã nhập", "có giá trị"],
    }

    @classmethod
    def classify_operators(cls, text: str) -> list[str]:
        """Identifies which advanced operators are likely referenced in natural language text."""
        detected = []
        text_lower = text.lower()
        for operator, kw_list in cls.NL_KEYWORDS.items():
            if any(kw in text_lower for kw in kw_list):
                detected.append(operator)
        return detected

    @classmethod
    def tokenize(cls, expression: str) -> list[str]:
        """Tokenizes conditional expression for parser consumption."""
        pattern = (
            r"\b(?:SUM|AVG|COUNT|MAX|MIN)\s*\([^)]*\)|"
            r"\(|\)|\bAND\b|\bOR\b|\bBETWEEN\b|\bIN\b|\bLIKE\b|\bNOT\s+EXISTS\b|\bEXISTS\b|"
            r"\bIS\s+NOT\s+NULL\b|\bIS\s+NULL\b|'[^']*'|[^,\s\(\)]+"
        )
        tokens = re.findall(pattern, expression, re.IGNORECASE)
        cleaned = []
        for t in tokens:
            t_strip = t.strip()
            t_upper = t_strip.upper()
            # Replace multiple spaces inside NOT EXISTS with single space
            t_upper = re.sub(r"\s+", " ", t_upper)
            if t_upper in (
                "AND", "OR", "BETWEEN", "IN", "LIKE", "EXISTS", "NOT EXISTS",
                "IS NULL", "IS NOT NULL", "(", ")"
            ):
                cleaned.append(t_upper)
            else:
                cleaned.append(t_strip)
        return cleaned

    @classmethod
    def parse(cls, expression: str) -> Union[LogicalNode, ConditionNode, None]:
        """
        Parses a logical expression into a tree of LogicalNode and ConditionNode.
        E.g., "age BETWEEN 18 AND 30 AND status IN ('active', 'pending')"
        """
        tokens = cls.tokenize(expression)
        if not tokens:
            return None

        idx = 0

        def peek() -> str | None:
            nonlocal idx
            return tokens[idx] if idx < len(tokens) else None

        def consume(expected: str | None = None) -> str:
            nonlocal idx
            tok = tokens[idx]
            idx += 1
            if expected and tok != expected:
                raise ValueError(f"Expected {expected}, got {tok}")
            return tok

        def parse_expr() -> Union[LogicalNode, ConditionNode]:
            # expr -> term ( OR term )*
            node = parse_term()
            while peek() == "OR":
                consume("OR")
                right = parse_term()
                if isinstance(node, LogicalNode) and node.connector == "OR":
                    node.children.append(right)
                else:
                    node = LogicalNode(connector="OR", children=[node, right])
            return node

        def parse_term() -> Union[LogicalNode, ConditionNode]:
            # term -> factor ( AND factor )*
            node = parse_factor()
            while peek() == "AND":
                consume("AND")
                right = parse_factor()
                if isinstance(node, LogicalNode) and node.connector == "AND":
                    node.children.append(right)
                else:
                    node = LogicalNode(connector="AND", children=[node, right])
            return node

        def parse_factor() -> Union[LogicalNode, ConditionNode]:
            # factor -> ( expr ) | condition
            if peek() == "(":
                consume("(")
                node = parse_expr()
                consume(")")
                return node
            return parse_condition()

        def parse_condition() -> ConditionNode:
            # Check for leading EXISTS or NOT EXISTS
            if peek() in ("EXISTS", "NOT EXISTS"):
                op = consume()
                consume("(")
                # Inside exists, we consume everything up to matching ) as value
                subquery_parts = []
                paren_count = 1
                while peek() is not None:
                    tok = consume()
                    if tok == "(":
                        paren_count += 1
                    elif tok == ")":
                        paren_count -= 1
                        if paren_count == 0:
                            break
                    subquery_parts.append(tok)
                subquery_str = " ".join(subquery_parts)
                return ConditionNode(column="", operator=op, values=[subquery_str])

            column = consume()
            op = peek()

            if op in ("IS NULL", "IS NOT NULL"):
                consume()
                return ConditionNode(column=column, operator=op, values=[])

            if op == "BETWEEN":
                consume()
                val1 = consume()
                consume("AND")
                val2 = consume()
                return ConditionNode(column=column, operator="BETWEEN", values=[val1, val2])

            if op == "IN":
                consume()
                consume("(")
                vals = []
                while peek() != ")":
                    tok = consume()
                    if tok != ",":
                        vals.append(tok)
                consume(")")
                return ConditionNode(column=column, operator="IN", values=vals)

            if op == "LIKE":
                consume()
                val = consume()
                return ConditionNode(column=column, operator="LIKE", values=[val])

            # Fallback for standard operators (=, >, <, etc.)
            if op is not None and not op in ("AND", "OR", ")"):
                consume()
                val = consume()
                return ConditionNode(column=column, operator=op, values=[val])

            # Just a bare column/condition
            return ConditionNode(column=column, operator="=", values=[])

        try:
            return parse_expr()
        except Exception:
            return None
