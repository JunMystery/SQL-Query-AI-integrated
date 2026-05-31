"""Fuzzy schema mapping corrections for generated SQL statements."""

from __future__ import annotations

import difflib
import re

from sqlbot_desktop.models.entities import TableInfo


class QueryCorrector:
    """Correct hallucinated table/column names in generated SQL queries."""

    SQL_KEYWORDS = {
        "select", "from", "where", "join", "on", "group", "by", "order", "having",
        "limit", "as", "and", "or", "not", "in", "is", "null", "like", "between",
        "exists", "count", "sum", "avg", "min", "max", "strftime", "inner",
        "left", "right", "outer", "cross", "union", "all", "desc", "asc",
        "count", "sum", "avg", "min", "max"
    }

    @classmethod
    def correct_query(cls, sql: str, tables: list[TableInfo]) -> str:
        """Analyze SQL string and correct any misspelled table or column names."""
        if not sql or not tables:
            return sql

        schema_table_map = {t.name.lower(): t.name for t in tables}
        corrected_sql = sql
        referenced_tables: set[str] = set()

        # 1. Identify and correct table names following FROM or JOIN keywords
        # Regex matches FROM/JOIN followed by a table identifier (handling optional backticks/double quotes)
        table_ref_pattern = re.compile(r"\b(from|join)\s+[`\"]?([a-zA-Z_][a-zA-Z0-9_]*)[`\"]?", re.IGNORECASE)
        
        # We find matches and correct them in the SQL query
        matches = list(table_ref_pattern.finditer(corrected_sql))
        # Process from right to left so indices remain valid after replacements
        for match in reversed(matches):
            keyword = match.group(1)
            table_token = match.group(2)
            table_token_lower = table_token.lower()
            
            if table_token_lower in schema_table_map:
                real_name = schema_table_map[table_token_lower]
                referenced_tables.add(real_name)
                if table_token != real_name:
                    # Replace just the token within the match range
                    start = match.start(2)
                    end = match.end(2)
                    corrected_sql = corrected_sql[:start] + real_name + corrected_sql[end:]
            else:
                # Run fuzzy matching for table name
                fuzzy_matches = difflib.get_close_matches(table_token, list(schema_table_map.values()), n=1, cutoff=0.6)
                if fuzzy_matches:
                    real_name = fuzzy_matches[0]
                    referenced_tables.add(real_name)
                    start = match.start(2)
                    end = match.end(2)
                    corrected_sql = corrected_sql[:start] + real_name + corrected_sql[end:]

        # 2. Tokenize query to identify other potential identifiers (columns)
        tokens = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", corrected_sql))
        potential_identifiers = {
            token for token in tokens
            if token.lower() not in cls.SQL_KEYWORDS and token.lower() not in schema_table_map
        }

        # If no tables were recognized, assume all tables in schema could be referenced
        if not referenced_tables:
            referenced_tables = {t.name for t in tables}

        # 3. Collect columns from the referenced tables
        column_map: dict[str, str] = {}
        for table in tables:
            if table.name in referenced_tables:
                for col in table.columns:
                    column_map[col.name.lower()] = col.name

        # 4. Correct column names
        for token in potential_identifiers:
            token_lower = token.lower()

            # If it exactly matches a column (case-insensitively), correct casing if needed
            if token_lower in column_map:
                real_name = column_map[token_lower]
                if token != real_name:
                    corrected_sql = re.sub(rf"\b{re.escape(token)}\b", real_name, corrected_sql)
            else:
                # Run fuzzy matching for column names
                fuzzy_matches = difflib.get_close_matches(token, list(column_map.values()), n=1, cutoff=0.65)
                if fuzzy_matches:
                    real_name = fuzzy_matches[0]
                    corrected_sql = re.sub(rf"\b{re.escape(token)}\b", real_name, corrected_sql)

        return corrected_sql
