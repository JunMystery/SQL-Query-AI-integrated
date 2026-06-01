"""Bounded JOIN safety checks for the visual query builder."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any

from sqlalchemy import text

from sqlbot_desktop.agents.schema_graph import SchemaGraph
from sqlbot_desktop.models.entities import TableInfo


JoinEdge = tuple[str, str, str, str]


@dataclass(frozen=True)
class JoinSafetyResult:
    """Result of a schema/data safety check for a candidate JOIN table."""

    ok: bool
    severity: str
    message: str
    join_edges: list[JoinEdge]
    matched_sample_rows: int = 0
    sample_limit: int = 200
    timed_out: bool = False


class JoinSafetyService:
    """Checks whether selecting columns from another table is likely safe."""

    _IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(
        self,
        sample_limit: int = 200,
        max_probe_seconds: float = 2.0,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self.sample_limit = sample_limit
        self.max_probe_seconds = max_probe_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[tuple[object, ...], tuple[float, JoinSafetyResult]] = {}

    def check_candidate(
        self,
        start_table: str,
        selected_tables: list[str],
        candidate_table: str,
        tables: list[TableInfo],
        connection: Any | None = None,
        dialect: str = "sqlite",
    ) -> JoinSafetyResult:
        """Validate a candidate table using schema graph first, then a bounded data probe."""
        if not start_table or not candidate_table:
            return self._danger("Thiếu bảng chính hoặc bảng cần kiểm tra.", [])

        if candidate_table == start_table or candidate_table in selected_tables:
            return JoinSafetyResult(True, "ok", "Bảng đã nằm trong truy vấn.", [], sample_limit=self.sample_limit)

        graph = SchemaGraph(tables)
        targets = sorted({table for table in [*selected_tables, candidate_table] if table and table != start_table})
        join_edges = graph.find_join_path(start_table, targets)

        reachable_tables = {start_table}
        for left_table, _, right_table, _ in join_edges:
            reachable_tables.add(left_table)
            reachable_tables.add(right_table)

        if candidate_table not in reachable_tables:
            return self._danger("Không tìm thấy JOIN path theo schema/FK.", join_edges)

        if connection is None:
            return JoinSafetyResult(
                True,
                "warning",
                "Chỉ xác minh theo schema; chưa có connection để dry-run dữ liệu.",
                join_edges,
                sample_limit=self.sample_limit,
            )

        cache_key = (
            start_table,
            tuple(sorted(selected_tables)),
            candidate_table,
            tuple(join_edges),
            dialect,
            self.sample_limit,
        )
        cached = self._read_cache(cache_key)
        if cached:
            return cached

        result = self._run_bounded_probe(connection, start_table, candidate_table, join_edges)
        self._cache[cache_key] = (time.monotonic(), result)
        return result

    def _run_bounded_probe(
        self,
        connection: Any,
        start_table: str,
        candidate_table: str,
        join_edges: list[JoinEdge],
    ) -> JoinSafetyResult:
        started_at = time.monotonic()
        try:
            probe_sql = self._build_probe_sql(start_table, join_edges)
            if not probe_sql:
                return JoinSafetyResult(
                    True,
                    "warning",
                    "JOIN path có tên bảng/cột không an toàn để dry-run tự động.",
                    join_edges,
                    sample_limit=self.sample_limit,
                )

            matched_rows = int(connection.execute(text(probe_sql)).scalar() or 0)
            timed_out = (time.monotonic() - started_at) > self.max_probe_seconds
            if timed_out:
                return JoinSafetyResult(
                    True,
                    "warning",
                    "Dry-run vượt quá thời gian giới hạn; vẫn cho phép chọn nhưng cần kiểm tra kết quả.",
                    join_edges,
                    matched_sample_rows=matched_rows,
                    sample_limit=self.sample_limit,
                    timed_out=True,
                )

            if matched_rows == 0:
                return JoinSafetyResult(
                    False,
                    "danger",
                    "Không tìm thấy dữ liệu khớp trong mẫu kiểm tra.",
                    join_edges,
                    matched_sample_rows=0,
                    sample_limit=self.sample_limit,
                )

            if matched_rows <= max(1, self.sample_limit // 40):
                return JoinSafetyResult(
                    True,
                    "warning",
                    "JOIN có rất ít dòng khớp trong mẫu kiểm tra.",
                    join_edges,
                    matched_sample_rows=matched_rows,
                    sample_limit=self.sample_limit,
                )

            return JoinSafetyResult(
                True,
                "ok",
                "JOIN path hợp lệ trong mẫu kiểm tra.",
                join_edges,
                matched_sample_rows=matched_rows,
                sample_limit=self.sample_limit,
            )
        except Exception as exc:
            return JoinSafetyResult(
                True,
                "warning",
                f"Không thể dry-run JOIN tự động: {exc}",
                join_edges,
                sample_limit=self.sample_limit,
            )

    def _build_probe_sql(self, start_table: str, join_edges: list[JoinEdge]) -> str:
        if not join_edges:
            return ""

        table_columns: dict[str, set[str]] = {}
        table_order = [start_table]
        seen_tables = {start_table}
        for left_table, left_col, right_table, right_col in join_edges:
            table_columns.setdefault(left_table, set()).add(left_col)
            table_columns.setdefault(right_table, set()).add(right_col)
            for table_name in (left_table, right_table):
                if table_name not in seen_tables:
                    table_order.append(table_name)
                    seen_tables.add(table_name)

        for table_name, columns in table_columns.items():
            if not self._safe_identifier(table_name) or not all(self._safe_identifier(col) for col in columns):
                return ""

        aliases = {table_name: f"t{idx}" for idx, table_name in enumerate(table_order)}
        subqueries = {
            table_name: self._sample_subquery(table_name, sorted(table_columns[table_name]), aliases[table_name])
            for table_name in table_order
            if table_name in table_columns
        }
        from_sql = subqueries[table_order[0]]
        joined_tables = {table_order[0]}
        joins = []
        for left_table, left_col, right_table, right_col in join_edges:
            left_alias = aliases[left_table]
            right_alias = aliases[right_table]
            condition = f"{left_alias}.{left_col} = {right_alias}.{right_col}"
            if left_table in joined_tables and right_table not in joined_tables:
                joins.append(f"JOIN {subqueries[right_table]} ON {condition}")
                joined_tables.add(right_table)
            elif right_table in joined_tables and left_table not in joined_tables:
                joins.append(f"JOIN {subqueries[left_table]} ON {condition}")
                joined_tables.add(left_table)
            elif left_table in joined_tables and right_table in joined_tables:
                continue
            else:
                joins.append(f"JOIN {subqueries[right_table]} ON {condition}")
                joined_tables.add(right_table)

        joined_sql = f"SELECT 1 FROM {from_sql} {' '.join(joins)} LIMIT {self.sample_limit}"
        return f"SELECT COUNT(*) FROM ({joined_sql}) joined_sample"

    def _sample_subquery(self, table_name: str, columns: list[str], alias: str) -> str:
        col_sql = ", ".join(columns)
        not_null = " AND ".join(f"{column} IS NOT NULL" for column in columns)
        return f"(SELECT {col_sql} FROM {table_name} WHERE {not_null} LIMIT {self.sample_limit}) {alias}"

    def _read_cache(self, key: tuple[object, ...]) -> JoinSafetyResult | None:
        cached = self._cache.get(key)
        if not cached:
            return None
        created_at, result = cached
        if time.monotonic() - created_at > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        return result

    def _danger(self, message: str, join_edges: list[JoinEdge]) -> JoinSafetyResult:
        return JoinSafetyResult(False, "danger", message, join_edges, sample_limit=self.sample_limit)

    def _safe_identifier(self, value: str) -> bool:
        return bool(self._IDENTIFIER_RE.match(value))
