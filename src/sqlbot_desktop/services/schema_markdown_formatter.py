"""Format linked schema metadata into compact Markdown for prompts."""

from __future__ import annotations

from collections import OrderedDict

from sqlbot_desktop.models.entities import ColumnMetadata


class SchemaMarkdownFormatter:
    """Render a subset schema in a stable, token-conscious format."""

    @staticmethod
    def format(columns: list[ColumnMetadata]) -> str:
        grouped: OrderedDict[str, list[ColumnMetadata]] = OrderedDict()
        for column in columns:
            grouped.setdefault(column.table_name, []).append(column)

        lines: list[str] = []
        for table_name, table_columns in grouped.items():
            lines.append(f"## Table: {table_name}")
            for column in table_columns:
                details = [column.data_type or "UNKNOWN"]
                if column.is_primary_key:
                    details.append("PK")
                if column.is_foreign_key:
                    fk_target = (
                        f"FK -> {column.referenced_table}.{column.referenced_column}"
                        if column.referenced_table and column.referenced_column
                        else "FK"
                    )
                    details.append(fk_target)
                suffix = SchemaMarkdownFormatter._suffix(column)
                lines.append(f"- {column.column_name} ({', '.join(details)}){suffix}")
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _suffix(column: ColumnMetadata) -> str:
        parts: list[str] = []
        if column.business_description:
            parts.append(column.business_description)
        if column.sample_values:
            samples = ", ".join(repr(value) for value in column.sample_values[:3])
            parts.append(f"ví dụ: {samples}")
        return f": {'; '.join(parts)}" if parts else ""
