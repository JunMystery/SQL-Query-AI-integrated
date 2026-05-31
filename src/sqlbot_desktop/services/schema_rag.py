"""Semantic schema matcher (local RAG-like lookup) for text-to-SQL."""

from __future__ import annotations

import re
from sqlbot_desktop.models.entities import TableInfo


class SchemaRAG:
    """Performs semantic keyword expansion and ranks relevant database tables for a given prompt."""

    # Conceptual dictionary for translating Vietnamese user terms to technical DB identifiers
    SYNONYMS: dict[str, list[str]] = {
        "task": ["habit", "completion", "todo", "task"],
        "tasks": ["habit", "completion", "todo", "task"],
        "công việc": ["habit", "completion", "todo", "task"],
        "thực hiện": ["completion", "completed", "done"],
        "hoàn thành": ["completion", "completed", "done"],
        "user": ["user", "username", "full_name"],
        "users": ["user", "username", "full_name"],
        "người dùng": ["user", "username", "full_name"],
        "tên": ["name", "username", "full_name", "title"],
        "họ tên": ["name", "username", "full_name"],
        "ngày": ["date", "time", "at", "created_at", "updated_at", "recorded_at", "from_date", "to_date"],
        "tháng": ["date", "time", "at", "created_at", "updated_at", "recorded_at"],
        "năm": ["date", "time", "at", "created_at", "updated_at", "recorded_at"],
        "thời gian": ["date", "time", "at", "created_at", "updated_at", "recorded_at"],
        "đọc": ["reading", "value"],
        "chỉ số": ["reading", "value"],
        "bệnh": ["disease"],
        "chats": ["chat", "session"],
        "tin nhắn": ["chat", "message", "history"],
        "hoạt động": ["activity", "history"],
        "lịch sử": ["history", "session"],
    }

    @classmethod
    def get_keywords(cls, prompt: str) -> set[str]:
        """Tokenize prompt and expand terms using the synonym dictionary."""
        words = re.findall(r"\b[a-zA-Z0-9_à-ỹÀ-Ỹ]+\b", prompt.lower())
        keywords = set(words)
        for word in words:
            if word in cls.SYNONYMS:
                keywords.update(cls.SYNONYMS[word])
        return keywords

    @classmethod
    def rank_tables(
        cls,
        prompt: str,
        tables: list[TableInfo],
        annotations: dict[str, object] | None = None
    ) -> list[TableInfo]:
        """Rank and return tables based on match relevance score for the query."""
        keywords = cls.get_keywords(prompt)
        scored_tables: list[tuple[float, TableInfo]] = []
        table_payloads = annotations.get("tables", {}) if isinstance(annotations, dict) else {}

        for table in tables:
            score = 0.0
            table_name_lower = table.name.lower()
            table_payload = table_payloads.get(table.name, {}) if isinstance(table_payloads, dict) else {}
            table_desc = str(table_payload.get("description", "")).lower() if isinstance(table_payload, dict) else ""

            # 1. Match table name
            for kw in keywords:
                if kw in table_name_lower:
                    score += 5.0
                if table_desc and kw in table_desc:
                    score += 3.0

            # 2. Match column names and descriptions
            column_payloads = table_payload.get("columns", {}) if isinstance(table_payload, dict) else {}
            for col in table.columns:
                col_name_lower = col.name.lower()
                col_payload = column_payloads.get(col.name, {}) if isinstance(column_payloads, dict) else {}
                col_desc = str(col_payload.get("description", "")).lower() if isinstance(col_payload, dict) else ""

                for kw in keywords:
                    if kw == col_name_lower:
                        score += 3.0
                    elif kw in col_name_lower:
                        score += 1.0
                    if col_desc and kw in col_desc:
                        score += 2.0

            # 3. Boost tables that link users/activities if the prompt mentions users/tasks
            has_user_mention = any(u in keywords for u in ["user", "users", "người dùng", "tên", "họ tên"])
            if has_user_mention:
                if "user" in table_name_lower or any(c.name.lower() == "user_id" for c in table.columns):
                    score += 2.0

            # Keep only tables with matching trace
            if score > 0:
                scored_tables.append((score, table))

        # Sort tables by score descending
        scored_tables.sort(key=lambda x: x[0], reverse=True)
        return [t[1] for t in scored_tables]

    @classmethod
    def get_rag_schema_context(
        cls,
        prompt: str,
        tables: list[TableInfo],
        annotations: dict[str, object] | None = None,
        max_tables: int = 5
    ) -> str:
        """Return a formatted schema string containing only the most relevant tables for the prompt."""
        ranked = cls.rank_tables(prompt, tables, annotations)
        # If no tables matched, fallback to returning the first few tables
        subset = ranked[:max_tables] if ranked else tables[:max_tables]

        lines: list[str] = []
        table_payloads = annotations.get("tables", {}) if isinstance(annotations, dict) else {}

        for table in subset:
            table_payload = table_payloads.get(table.name, {}) if isinstance(table_payloads, dict) else {}
            desc = table_payload.get("description", "") if isinstance(table_payload, dict) else ""
            desc_part = f" ({desc})" if desc else ""
            cols = ", ".join(col.name for col in table.columns)
            lines.append(f"- Bảng `{table.name}`{desc_part}: các cột [{cols}]")

        return "\n".join(lines)
