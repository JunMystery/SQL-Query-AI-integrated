"""Orchestrator module to coordinate all agent operations to build and validate SQL queries."""

from __future__ import annotations
from typing import Any
from sqlbot_desktop.models.entities import TableInfo, ColumnMetadata
from sqlbot_desktop.agents.schema_graph import SchemaGraph
from sqlbot_desktop.agents.join_planner import JoinPlanner
from sqlbot_desktop.agents.operator_classifier import OperatorClassifier
from sqlbot_desktop.agents.grouping_handler import GroupingHandler
from sqlbot_desktop.agents.subquery_generator import SubqueryGenerator
from sqlbot_desktop.agents.setop_handler import SetOpHandler
from sqlbot_desktop.agents.correction_loop import CorrectionLoop


class Orchestrator:
    """
    Coordinates all specialized agents/handlers (Router, JoinPlanner, FilterAgent,
    AggregationAgent, SetOpAgent, Validator/CorrectionLoop) to translate
    natural language questions into syntactically correct and validated SQL.
    """

    def __init__(
        self,
        metadata_list: list[ColumnMetadata] | list[TableInfo],
        ai_engine: Any = None,
        db_connection: Any = None,
        dialect: str = "sqlite"
    ) -> None:
        self.metadata_list = metadata_list
        self.schema_graph = SchemaGraph(metadata_list)
        self.join_planner = JoinPlanner(self.schema_graph)
        self.correction_loop = CorrectionLoop(ai_engine)
        self.db_connection = db_connection
        self.dialect = dialect

    def orchestrate(
        self,
        question: str,
        start_table: str,
        target_tables: list[str],
        select_columns: list[str],
        filter_expression: str | None = None,
        join_overrides: dict[str, str] | None = None
    ) -> str:
        """
        Coordinates the pipeline:
          1. Detects set operations (SetOpAgent/Router)
          2. Maps out join paths (JoinPlanner)
          3. Parses/extracts conditions (FilterAgent/OperatorClassifier)
          4. Applies grouping/aggregations (AggregationAgent/GroupingHandler)
          5. Generates subqueries if necessary (SubqueryGenerator)
          6. Stitches the final SQL
          7. Validates and corrects the SQL (Validator/CorrectionLoop)
        """
        # 1. Set operation check (Router / SetOpAgent)
        set_op = SetOpHandler.detect_set_op(question)
        if set_op and ";" in question:
            # If the user prompt lists multiple sub-prompts divided by semicolon, stitch them
            sub_parts = [part.strip() for part in question.split(";") if part.strip()]
            queries = []
            for part in sub_parts:
                # Recursively generate query for each part
                q_sub = self._build_single_query(
                    start_table, target_tables, select_columns, filter_expression, join_overrides
                )
                queries.append(q_sub)
            raw_sql = SetOpHandler.stitch_queries(queries, set_op)
        else:
            raw_sql = self._build_single_query(
                start_table, target_tables, select_columns, filter_expression, join_overrides
            )

        # 2. Validation & self-correction loop
        validated_sql = self.correction_loop.validate_and_correct(
            query=raw_sql,
            dialect=self.dialect,
            db_connection=self.db_connection,
            prompt_context=question
        )

        return validated_sql

    def _build_single_query(
        self,
        start_table: str,
        target_tables: list[str],
        select_columns: list[str],
        filter_expression: str | None = None,
        join_overrides: dict[str, str] | None = None
    ) -> str:
        # Generate Join Clauses
        plan = self.join_planner.plan_joins(start_table, target_tables, join_overrides)
        join_clauses = plan["join_clauses"]
        aliases = plan["aliases"]

        # Alias the selected columns
        aliased_selects = []
        import re
        for col in select_columns:
            aliased_col = col
            found = False
            for tbl, alias in aliases.items():
                if f"{tbl}." in aliased_col:
                    aliased_col = re.sub(rf"\b{tbl}\.", f"{alias}.", aliased_col)
                    found = True
            if not found:
                start_alias = aliases.get(start_table, "t")
                func_match = re.match(r"^(\w+)\s*\(([^)]+)\)(.*)$", aliased_col)
                if func_match:
                    func_name, arg, rest = func_match.groups()
                    if not any(f"{al}." in arg for al in aliases.values()):
                        aliased_col = f"{func_name}({start_alias}.{arg.strip()}){rest}"
                else:
                    aliased_col = f"{start_alias}.{aliased_col}"
            aliased_selects.append(aliased_col)

        # Extract WHERE and HAVING conditions
        where_conds = []
        having_conds = []
        if filter_expression:
            # Parse filter tree
            parsed_tree = OperatorClassifier.parse(filter_expression)
            # Reconstruct filters list
            filters_list = []
            if parsed_tree:
                # Simple condition or flatten and/or list
                if hasattr(parsed_tree, "children"):
                    for child in parsed_tree.children:
                        filters_list.append(self._format_condition_node(child, aliases, start_table))
                else:
                    filters_list.append(self._format_condition_node(parsed_tree, aliases, start_table))
            else:
                filters_list.append(filter_expression)

            where_conds, having_conds = GroupingHandler.formulate_having(filters_list)

        # Build SQL structure
        sql_parts = ["SELECT " + ", ".join(aliased_selects)]
        start_alias = aliases.get(start_table, "t")
        sql_parts.append(f"FROM {start_table} {start_alias}")

        if join_clauses:
            sql_parts.extend(join_clauses)

        if where_conds:
            sql_parts.append("WHERE " + " AND ".join(where_conds))

        # Check for GROUP BY columns
        group_by = GroupingHandler.parse_group_by(aliased_selects)
        if group_by:
            sql_parts.append("GROUP BY " + ", ".join(group_by))

        if having_conds:
            sql_parts.append("HAVING " + " AND ".join(having_conds))

        return " ".join(sql_parts)

    def _format_condition_node(self, node: Any, aliases: dict[str, str], start_table: str) -> str:
        if not hasattr(node, "column") or not hasattr(node, "operator"):
            return str(node)
        col = node.column
        op = node.operator
        vals = node.values
        import re

        # Resolve alias for node column
        aliased_col = col
        if col:
            found = False
            for tbl, alias in aliases.items():
                if f"{tbl}." in aliased_col:
                    aliased_col = re.sub(rf"\b{tbl}\.", f"{alias}.", aliased_col)
                    found = True
            if not found:
                start_alias = aliases.get(start_table, "t")
                func_match = re.match(r"^(\w+)\s*\(([^)]+)\)$", aliased_col)
                if func_match:
                    func_name, arg = func_match.groups()
                    if not any(f"{al}." in arg for al in aliases.values()):
                        aliased_col = f"{func_name}({start_alias}.{arg.strip()})"
                elif not any(f"{al}." in aliased_col for al in aliases.values()):
                    aliased_col = f"{start_alias}.{aliased_col}"

        if op == "BETWEEN" and len(vals) >= 2:
            return f"{aliased_col} BETWEEN {vals[0]} AND {vals[1]}"
        elif op == "IN":
            return f"{aliased_col} IN ({', '.join(vals)})"
        elif op == "LIKE" and vals:
            return f"{aliased_col} LIKE {vals[0]}"
        elif op in ("IS NULL", "IS NOT NULL"):
            return f"{aliased_col} {op}"
        elif op == "EXISTS" and vals:
            return f"EXISTS ({vals[0]})"
        elif vals:
            return f"{aliased_col} {op} {vals[0]}"
        return f"{aliased_col} = ''"
