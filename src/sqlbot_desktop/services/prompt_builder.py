"""Prompt construction for Vietnamese text-to-SQL."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlbot_desktop.models.entities import TableInfo


SYSTEM_PROMPT = """You are an expert Text-to-SQL assistant.

Mandatory rules:
1. Generate SELECT statements only. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, MERGE, EXEC, GRANT, or REVOKE.
2. Use only table names and column names that appear in the provided SCHEMA.
3. Do not invent tables, columns, joins, filters, or business meanings.
4. Do not copy table or column names from examples unless those names also appear in the provided SCHEMA.
5. Preserve literal values exactly as they appear in the user's question or in database samples, including Vietnamese diacritics.
6. Prefer joins only when a foreign key or explicit relationship is provided.
7. Return valid SQL only. Do not include prose outside SQL.
8. Reply in Vietnamese.
"""


DEFAULT_FEW_SHOT_EXAMPLES = [
    {
        "question": "Liệt kê tên và lương của nhân viên phòng Kế toán",
        "sql": """SELECT nv.ho_ten, nv.luong
FROM nhan_vien nv
JOIN phong_ban pb ON nv.phong_ban_id = pb.id
WHERE pb.ten_phong = N'Kế toán';""",
    },
    {
        "question": "Tính tổng doanh thu theo từng tháng trong năm 2025",
        "sql": """SELECT
    strftime('%m', ngay_tao) AS thang,
    SUM(tong_tien) AS tong_doanh_thu
FROM don_hang
WHERE strftime('%Y', ngay_tao) = '2025'
GROUP BY strftime('%m', ngay_tao)
ORDER BY thang;""",
    },
]


class PromptBuilder:
    """Build compact prompts for local or API AI backends."""

    @staticmethod
    def system_prompt() -> str:
        return SYSTEM_PROMPT

    @staticmethod
    def build(
        question: str,
        schema_context: str = "",
        dialect: str = "",
        *,
        error_message: str = "",
        few_shot_examples: Sequence[Mapping[str, object]] | None = None,
    ) -> str:
        schema_block = schema_context or "Schema is not available. Generate SQL only when enough context is available."
        dialect_block = PromptBuilder._dialect_label(dialect)
        examples = PromptBuilder._few_shot_block(
            few_shot_examples if few_shot_examples is not None else DEFAULT_FEW_SHOT_EXAMPLES
        )
        error_block = PromptBuilder._error_block(error_message)
        example_block = (
            "SYNTAX EXAMPLES:\n"
            f"{examples}\n\n"
            if examples
            else ""
        )
        return (
            f"{SYSTEM_PROMPT}\n"
            f"DIALECT: {dialect_block}\n\n"
            f"SCHEMA:\n{schema_block}\n\n"
            "NOTE: Examples are syntax references only. Use only tables and columns that appear in SCHEMA.\n\n"
            f"{example_block}"
            f"{error_block}"
            f"USER QUESTION:\n{question.strip()}\n\n"
            "SQL:"
        )

    @staticmethod
    def build_schema_context(tables: list[TableInfo], annotations: dict[str, object] | None = None) -> str:
        table_payloads = PromptBuilder._annotation_tables(annotations)
        lines: list[str] = []
        for table_info in tables:
            table_payload = table_payloads.get(table_info.name, {})
            table_description = PromptBuilder._text(table_payload.get("description")) if table_payload else ""
            table_label = f"{table_description} [{table_info.name}]" if table_description else table_info.name
            lines.append(f"- TABLE {table_label}")

            column_payloads = table_payload.get("columns", {}) if isinstance(table_payload, dict) else {}
            for column in table_info.columns:
                column_payload = column_payloads.get(column.name, {}) if isinstance(column_payloads, dict) else {}
                description = PromptBuilder._text(column_payload.get("description")) if isinstance(column_payload, dict) else ""
                unit = PromptBuilder._text(column_payload.get("unit")) if isinstance(column_payload, dict) else ""
                note = PromptBuilder._text(column_payload.get("note")) if isinstance(column_payload, dict) else ""
                type_name = PromptBuilder._text(column_payload.get("type")) if isinstance(column_payload, dict) else ""
                type_name = type_name or column.type_name

                details = [f"real_name={column.name}"]
                if type_name:
                    details.append(f"type={type_name}")
                if description:
                    details.append(f"description={description}")
                if unit:
                    details.append(f"unit={unit}")
                if note:
                    details.append(f"note={note}")
                lines.append(f"  - COLUMN {'; '.join(details)}")

        return "\n".join(lines)

    @staticmethod
    def _few_shot_block(examples: Sequence[Mapping[str, object]]) -> str:
        blocks = []
        for example in examples:
            question = PromptBuilder._text(example.get("question"))
            sql = PromptBuilder._text(example.get("sql"))
            if question and sql:
                blocks.append(f"Q: {question}\nSQL:\n{sql}")
        return "\n\n".join(blocks)

    @staticmethod
    def _error_block(error_message: str) -> str:
        cleaned = error_message.strip()
        if not cleaned:
            return ""
        return (
            "PREVIOUS SQL ERROR:\n"
            f"{cleaned}\n"
            "Fix the SQL. The next answer must still be one valid SELECT statement only.\n\n"
        )

    @staticmethod
    def _dialect_label(dialect: str) -> str:
        normalized = dialect.strip().upper()
        if normalized == "MYSQL":
            return "MySQL/MariaDB"
        if normalized == "POSTGRESQL":
            return "PostgreSQL"
        return dialect.strip() or "SQL"

    @staticmethod
    def _annotation_tables(annotations: dict[str, object] | None) -> dict[str, dict[str, object]]:
        if not annotations:
            return {}
        tables = annotations.get("tables", {})
        if not isinstance(tables, dict):
            return {}
        return {str(name): payload for name, payload in tables.items() if isinstance(payload, dict)}

    @staticmethod
    def _text(value: object) -> str:
        return str(value).strip() if value is not None else ""
