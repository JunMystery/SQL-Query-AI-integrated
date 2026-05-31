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
        """Return a formatted schema string containing only the most relevant tables and their relations."""
        ranked = cls.rank_tables(prompt, tables, annotations)
        # If no tables matched, fallback to returning the first few tables
        subset = ranked[:max_tables] if ranked else tables[:max_tables]
        subset_names = {t.name for t in subset}

        lines: list[str] = []
        table_payloads = annotations.get("tables", {}) if isinstance(annotations, dict) else {}

        # 1. Output table columns
        for table in subset:
            table_payload = table_payloads.get(table.name, {}) if isinstance(table_payloads, dict) else {}
            desc = table_payload.get("description", "") if isinstance(table_payload, dict) else ""
            desc_part = f" ({desc})" if desc else ""
            
            # Format columns with key markers and data profiling details if available
            cols_formatted = []
            for col in table.columns:
                marker = ""
                if getattr(col, "is_primary", False):
                    marker = " (PK)"
                elif getattr(col, "is_foreign", False):
                    marker = " (FK)"
                
                # Retrieve profile properties
                profile_details = []
                sample_val = getattr(col, "sample_value", "")
                enum_vals = getattr(col, "enum_values", [])
                
                if enum_vals:
                    profile_details.append(f"giá trị: {', '.join(repr(v) for v in enum_vals)}")
                elif sample_val:
                    profile_details.append(f"ví dụ: {repr(sample_val)}")
                
                profile_str = f" [{'; '.join(profile_details)}]" if profile_details else ""
                cols_formatted.append(f"{col.name}{marker}{profile_str}")
                
            cols_str = ", ".join(cols_formatted)
            lines.append(f"- Bảng `{table.name}`{desc_part}: các cột [{cols_str}]")

        # 2. Output relationships (Physical & Logical)
        relations: set[str] = set()
        
        # Physical Foreign Keys
        for table in subset:
            for fk in getattr(table, "foreign_keys", []):
                t_from = fk.get("constrained_table", "")
                c_from = fk.get("constrained_column", "")
                t_to = fk.get("referred_table", "")
                c_to = fk.get("referred_column", "")
                if t_from in subset_names and t_to in subset_names:
                    relations.add(f"- Bảng `{t_from}` (cột `{c_from}`) -> Bảng `{t_to}` (cột `{c_to}`)")

        # Logical Foreign Keys Fallback
        # If no physical FKs found between these tables, try to infer them logically (e.g. users.user_id = tasks.user_id)
        for i, t1 in enumerate(subset):
            for t2 in subset[i+1:]:
                # Check for columns with identical names and ending with _id
                for col1 in t1.columns:
                    for col2 in t2.columns:
                        if col1.name.lower() == col2.name.lower() and col1.name.lower().endswith("_id"):
                            # Prevent duplicates or self references
                            fk_str1 = f"- Bảng `{t1.name}` (cột `{col1.name}`) -> Bảng `{t2.name}` (cột `{col2.name}`)"
                            fk_str2 = f"- Bảng `{t2.name}` (cột `{col2.name}`) -> Bảng `{t1.name}` (cột `{col1.name}`)"
                            if fk_str1 not in relations and fk_str2 not in relations:
                                relations.add(fk_str1)

        if relations:
            lines.append("\n-- CÁC LIÊN KẾT LIÊN BẢNG HỢP LỆ (FOREIGN KEYS) - CHỈ JOIN THEO CÁC LIÊN KẾT NÀY:")
            for rel in sorted(relations):
                lines.append(rel)

        return "\n".join(lines)
