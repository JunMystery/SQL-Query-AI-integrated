"""Prompt construction for Vietnamese text-to-SQL."""

from __future__ import annotations

from sqlbot_desktop.models.entities import TableInfo


SYSTEM_PROMPT = """Bạn là chuyên gia SQL chuyển đổi câu hỏi tiếng Việt thành câu lệnh SQL.

QUY TẮC:
1. Chỉ tạo câu lệnh SELECT. KHÔNG tạo INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE.
2. Sử dụng đúng tên bảng và cột thật từ schema được cung cấp.
3. Với tiếng Việt có dấu, giữ nguyên giá trị như trong database.
4. Ưu tiên JOIN thay vì subquery khi có thể.
5. Nếu query phức tạp, có thể thêm comment SQL ngắn bằng cú pháp --.

ĐẦU RA:
Chỉ trả về câu lệnh SQL hợp lệ, không giải thích bên ngoài SQL.
"""


FEW_SHOT_EXAMPLES = [
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
    """Build prompts for local or API AI backends."""

    @staticmethod
    def system_prompt() -> str:
        return SYSTEM_PROMPT

    @staticmethod
    def build(question: str, schema_context: str = "", dialect: str = "") -> str:
        schema_block = schema_context or "Schema chưa được tải. Chỉ tạo SQL khi có đủ ngữ cảnh."
        dialect_block = PromptBuilder._dialect_label(dialect)
        examples = PromptBuilder._few_shot_block()
        return (
            f"DIALECT: {dialect_block}\n\n"
            f"SCHEMA:\n{schema_block}\n\n"
            f"VÍ DỤ:\n{examples}\n\n"
            f"CÂU HỎI:\n{question.strip()}\n\n"
            "SQL:"
        )

    @staticmethod
    def build_schema_context(tables: list[TableInfo], annotations: dict[str, object] | None = None) -> str:
        table_payloads = PromptBuilder._annotation_tables(annotations)
        lines: list[str] = []
        for table in tables:
            table_payload = table_payloads.get(table.name, {})
            table_description = PromptBuilder._text(table_payload.get("description")) if table_payload else ""
            table_label = f"{table_description} [{table.name}]" if table_description else table.name
            lines.append(f"- TABLE {table_label}")

            column_payloads = table_payload.get("columns", {}) if isinstance(table_payload, dict) else {}
            for column in table.columns:
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
    def _few_shot_block() -> str:
        blocks = []
        for example in FEW_SHOT_EXAMPLES:
            blocks.append(f"Q: {example['question']}\nSQL:\n{example['sql']}")
        return "\n\n".join(blocks)

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
