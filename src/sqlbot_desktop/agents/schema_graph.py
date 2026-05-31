"""Schema Graph module for finding minimal join paths between tables."""

from __future__ import annotations
from collections import defaultdict, deque
from sqlbot_desktop.models.entities import ColumnMetadata, TableInfo


class SchemaGraph:
    """
    Builds an in-memory graph where nodes are tables and edges represent
    foreign key relationships (explicit or naming-convention based fallbacks).
    Provides a BFS-based minimal join path finder.
    """

    def __init__(self, metadata_list: list[ColumnMetadata] | list[TableInfo]) -> None:
        self.tables: dict[str, dict[str, dict[str, bool]]] = {}
        self.explicit_edges: list[tuple[str, str, str, str]] = []

        if not metadata_list:
            return

        # Check type of first element to decide parsing strategy
        first_item = metadata_list[0]
        if isinstance(first_item, ColumnMetadata):
            self._parse_column_metadata(metadata_list)  # type: ignore
        else:
            self._parse_table_info(metadata_list)  # type: ignore

    def _parse_column_metadata(self, columns: list[ColumnMetadata]) -> None:
        for col in columns:
            t_name = col.table_name
            c_name = col.column_name
            if t_name not in self.tables:
                self.tables[t_name] = {}
            self.tables[t_name][c_name] = {
                "is_primary": col.is_primary_key,
                "is_foreign": col.is_foreign_key,
                "nullable": not col.is_primary_key,  # Default fallback for metadata
            }
            if col.is_foreign_key and col.referenced_table and col.referenced_column:
                self.explicit_edges.append((t_name, c_name, col.referenced_table, col.referenced_column))

    def _parse_table_info(self, tables: list[TableInfo]) -> None:
        for table in tables:
            t_name = table.name
            if t_name not in self.tables:
                self.tables[t_name] = {}
            for col in table.columns:
                self.tables[t_name][col.name] = {
                    "is_primary": getattr(col, "is_primary", False),
                    "is_foreign": getattr(col, "is_foreign", False),
                    "nullable": getattr(col, "nullable", True) if getattr(col, "nullable", True) is not None else True,
                }
            for fk in getattr(table, "foreign_keys", []):
                t_from = fk.get("constrained_table", "")
                c_from = fk.get("constrained_column", "")
                t_to = fk.get("referred_table", "")
                c_to = fk.get("referred_column", "")
                if t_from and c_from and t_to and c_to:
                    self.explicit_edges.append((t_from, c_from, t_to, c_to))

    def _get_fallback_edges(self) -> list[tuple[str, str, str, str]]:
        """
        Generates logical edges based on naming convention fallbacks.
        E.g., table A has column 'id', table B has column 'table_a_id'.
        Or both tables share a column ending in '_id' (like 'user_id').
        """
        fallback = []
        table_names = list(self.tables.keys())

        for i, t1 in enumerate(table_names):
            for t2 in table_names[i + 1:]:
                for col1 in self.tables[t1]:
                    for col2 in self.tables[t2]:
                        c1_lower = col1.lower()
                        c2_lower = col2.lower()
                        t1_lower = t1.lower()
                        t2_lower = t2.lower()

                        # 1. Identical names ending with _id
                        if c1_lower == c2_lower and c1_lower.endswith("_id"):
                            fallback.append((t1, col1, t2, col2))
                            continue

                        # 2. t1 has "id" and t2 has "t1_id" or "t1_singular_id"
                        if c1_lower == "id":
                            t1_singular = t1_lower[:-1] if t1_lower.endswith("s") else t1_lower
                            if c2_lower == f"{t1_lower}_id" or c2_lower == f"{t1_singular}_id":
                                fallback.append((t1, col1, t2, col2))
                                continue

                        # 3. t2 has "id" and t1 has "t2_id" or "t2_singular_id"
                        if c2_lower == "id":
                            t2_singular = t2_lower[:-1] if t2_lower.endswith("s") else t2_lower
                            if c1_lower == f"{t2_lower}_id" or c1_lower == f"{t2_singular}_id":
                                fallback.append((t1, col1, t2, col2))
                                continue
        return fallback

    def _bfs(self, start: str, target: str, edges: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]] | None:
        """Helper to find the shortest path from start to target using BFS on a set of edges."""
        adj = defaultdict(list)
        for edge in edges:
            t_from, c_from, t_to, c_to = edge
            adj[t_from].append((t_to, t_from, c_from, t_to, c_to))
            adj[t_to].append((t_from, t_to, c_to, t_from, c_from))

        queue = deque([(start, [])])
        visited = {start}

        while queue:
            current, path = queue.popleft()
            if current == target:
                return path

            for neighbor, src_t, src_c, tgt_t, tgt_c in adj[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [(src_t, src_c, tgt_t, tgt_c)]))

        return None

    def find_join_path(self, start_table: str, target_tables: list[str]) -> list[tuple[str, str, str, str]]:
        """
        Finds a minimal join path from start_table to all target_tables.
        Returns a list of unique join tuples (source_table, source_column, target_table, target_column).
        """
        if not target_tables:
            return []

        if start_table not in self.tables:
            return []

        resolved_edges: list[tuple[str, str, str, str]] = []
        seen_edges: set[tuple[str, str, str, str]] = set()

        fallback_edges = self._get_fallback_edges()

        for target in target_tables:
            if target not in self.tables:
                continue
            if target == start_table:
                continue

            # Try finding path using explicit edges first
            path = self._bfs(start_table, target, self.explicit_edges)
            if not path:
                # Fallback to explicit + fallback edges
                path = self._bfs(start_table, target, self.explicit_edges + fallback_edges)

            if path:
                for edge in path:
                    t1, c1, t2, c2 = edge
                    norm_key1 = (t1, c1, t2, c2)
                    norm_key2 = (t2, c2, t1, c1)
                    if norm_key1 not in seen_edges and norm_key2 not in seen_edges:
                        resolved_edges.append(edge)
                        seen_edges.add(norm_key1)

        return resolved_edges
