"""Join Planner module to generate SQL join clauses with aliases and correct join types."""

from __future__ import annotations
from sqlbot_desktop.agents.schema_graph import SchemaGraph


class JoinPlanner:
    """
    Maps out join paths using a SchemaGraph, assigns table aliases,
    and automatically determines join types (INNER, LEFT, RIGHT, FULL OUTER).
    """

    def __init__(self, schema_graph: SchemaGraph) -> None:
        self.schema_graph = schema_graph

    def generate_aliases(self, tables: list[str]) -> dict[str, str]:
        """Generates unique short aliases for a list of table names."""
        aliases = {}
        seen = set()
        for t in tables:
            # Generate base alias from first letters of underscore-separated parts
            parts = t.split("_")
            base = "".join(p[0] for p in parts if p).lower()
            if not base:
                base = "t"
            alias = base
            counter = 1
            while alias in seen:
                alias = f"{base}{counter}"
                counter += 1
            seen.add(alias)
            aliases[t] = alias
        return aliases

    def plan_joins(
        self,
        start_table: str,
        target_tables: list[str],
        join_types_override: dict[str, str] | None = None
    ) -> dict[str, any]:
        """
        Plans joins from start_table to target_tables.
        Returns a dict containing:
          - 'join_clauses': list of SQL string join clauses (e.g. "LEFT JOIN orders o ON u.id = o.user_id")
          - 'aliases': dict mapping table name to alias
        """
        override = join_types_override or {}
        
        # Get path of edges
        edges = self.schema_graph.find_join_path(start_table, target_tables)
        
        # Gather all tables involved in the path to generate aliases
        all_tables = [start_table]
        for t1, _, t2, _ in edges:
            if t1 not in all_tables:
                all_tables.append(t1)
            if t2 not in all_tables:
                all_tables.append(t2)
                
        aliases = self.generate_aliases(all_tables)
        
        joined_tables = {start_table}
        join_clauses = []
        
        for t1, c1, t2, c2 in edges:
            # Determine which table is the new one
            if t1 in joined_tables and t2 not in joined_tables:
                new_table, new_col = t2, c2
                old_table, old_col = t1, c1
            elif t2 in joined_tables and t1 not in joined_tables:
                new_table, new_col = t1, c1
                old_table, old_col = t2, c2
            else:
                # Both already joined or neither joined (should not happen with BFS)
                continue

            # Determine JOIN type
            # 1. Check override
            if new_table in override:
                join_type = override[new_table].upper()
            elif f"{old_table}->{new_table}" in override:
                join_type = override[f"{old_table}->{new_table}"].upper()
            else:
                # 2. Check nullability of joining columns
                col1_nullable = self.schema_graph.tables.get(t1, {}).get(c1, {}).get("nullable", True)
                col2_nullable = self.schema_graph.tables.get(t2, {}).get(c2, {}).get("nullable", True)
                if col1_nullable or col2_nullable:
                    join_type = "LEFT"
                else:
                    join_type = "INNER"

            new_alias = aliases[new_table]
            old_alias = aliases[old_table]
            
            clause = f"{join_type} JOIN {new_table} {new_alias} ON {old_alias}.{old_col} = {new_alias}.{new_col}"
            join_clauses.append(clause)
            joined_tables.add(new_table)

        return {
            "join_clauses": join_clauses,
            "aliases": aliases
        }
