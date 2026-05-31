"""Persistence for schema annotations."""

from __future__ import annotations

import json
from pathlib import Path
import re

from sqlbot_desktop.models.entities import TableInfo


class AnnotationRepository:
    """Read and write per-connection schema annotations."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path("data/annotations")

    def path_for(self, connection_name: str) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", connection_name).strip("_")
        return self.base_dir / f"{safe_name or 'connection'}.annotations.json"

    def load(self, connection_name: str) -> dict[str, object]:
        path = self.path_for(connection_name)
        if not path.exists():
            return {"connection_name": connection_name, "tables": {}}
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            return {"connection_name": connection_name, "tables": {}}

    def save(self, connection_name: str, annotations: dict[str, object]) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(connection_name)
        payload = {"connection_name": connection_name, "tables": annotations.get("tables", {})}
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return path

    def empty_for_schema(self, connection_name: str, tables: list[TableInfo]) -> dict[str, object]:
        return {
            "connection_name": connection_name,
            "tables": {
                table.name: {
                    "description": "",
                    "columns": {
                        column.name: {
                            "description": "",
                            "unit": "",
                            "note": "",
                            "type": column.type_name,
                        }
                        for column in table.columns
                    },
                }
                for table in tables
            },
        }
