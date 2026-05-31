"""JSONL query-attempt logging for self-correction debugging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path


@dataclass(frozen=True)
class QueryAttempt:
    question: str
    attempt: int
    sql: str = ""
    error: str = ""
    success: bool = False


class QueryLogger:
    """Persist self-correction attempts without credentials or connection strings."""

    def __init__(self, log_dir: Path | str = "logs/queries") -> None:
        self.log_dir = Path(log_dir)

    def log_attempt(self, attempt: QueryAttempt) -> Path:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        path = self.log_dir / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
        payload = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "question": attempt.question,
            "attempt": attempt.attempt,
            "sql": attempt.sql,
            "error": attempt.error,
            "success": attempt.success,
        }
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return path
