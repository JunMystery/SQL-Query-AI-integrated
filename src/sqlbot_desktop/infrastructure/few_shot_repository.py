"""JSON persistence and selection for few-shot text-to-SQL examples."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re

from sqlbot_desktop.services.embedding_service import EmbeddingModel, cosine_similarity


@dataclass(frozen=True)
class FewShotExample:
    """A reusable text-to-SQL example."""

    question: str
    sql: str
    dialect: str = ""
    tags: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list)

    def to_prompt_dict(self) -> dict[str, str]:
        return {"question": self.question, "sql": self.sql}


class FewShotRepository:
    """Load and select few-shot examples from JSON."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/few_shot_examples.json")

    def load_examples(self) -> list[FewShotExample]:
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            return []
        items = payload.get("examples", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []
        return [example for item in items if isinstance(item, dict) and (example := self._from_dict(item))]

    def save_examples(self, examples: list[FewShotExample]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"examples": [self._to_dict(example) for example in examples]}
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return self.path

    def select_examples(
        self,
        question: str,
        dialect: str = "",
        limit: int = 3,
        embedding_model: EmbeddingModel | None = None,
    ) -> list[FewShotExample]:
        examples = self.load_examples()
        if not examples:
            return []

        filtered = self._filter_by_dialect(examples, dialect)
        if embedding_model:
            selected = self._select_by_embedding(question, filtered, limit, embedding_model)
            if selected:
                return selected
        return self._select_by_keywords(question, filtered, limit)

    def _select_by_embedding(
        self,
        question: str,
        examples: list[FewShotExample],
        limit: int,
        embedding_model: EmbeddingModel,
    ) -> list[FewShotExample]:
        question_vector = embedding_model.embed_text(question)
        scored = [
            (cosine_similarity(question_vector, example.embedding), example)
            for example in examples
            if example.embedding
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [example for score, example in scored[:limit] if score > 0]

    def _select_by_keywords(self, question: str, examples: list[FewShotExample], limit: int) -> list[FewShotExample]:
        keywords = set(re.findall(r"[\w]+", question.lower(), flags=re.UNICODE))
        scored: list[tuple[int, FewShotExample]] = []
        for example in examples:
            haystack = " ".join([example.question, " ".join(example.tags)]).lower()
            score = sum(1 for keyword in keywords if keyword and keyword in haystack)
            scored.append((score, example))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [example for score, example in scored[:limit] if score > 0] or examples[:limit]

    def _filter_by_dialect(self, examples: list[FewShotExample], dialect: str) -> list[FewShotExample]:
        normalized = dialect.strip().upper()
        if not normalized:
            return examples
        filtered = [example for example in examples if not example.dialect or example.dialect.strip().upper() == normalized]
        return filtered or examples

    def _from_dict(self, item: dict[str, object]) -> FewShotExample | None:
        question = str(item.get("question", "")).strip()
        sql = str(item.get("sql", "")).strip()
        if not question or not sql:
            return None
        tags = item.get("tags", [])
        embedding = item.get("embedding", [])
        return FewShotExample(
            question=question,
            sql=sql,
            dialect=str(item.get("dialect", "")).strip(),
            tags=[str(tag) for tag in tags] if isinstance(tags, list) else [],
            embedding=[float(value) for value in embedding] if isinstance(embedding, list) else [],
        )

    def _to_dict(self, example: FewShotExample) -> dict[str, object]:
        return {
            "question": example.question,
            "sql": example.sql,
            "dialect": example.dialect,
            "tags": example.tags,
            "embedding": example.embedding,
        }
