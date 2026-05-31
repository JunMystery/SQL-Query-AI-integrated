"""Example Store module to save and query few-shot text-to-SQL examples."""

from __future__ import annotations
from sqlbot_desktop.infrastructure.few_shot_repository import FewShotExample, FewShotRepository
from sqlbot_desktop.services.embedding_service import EmbeddingModel


class ExampleStore:
    """
    Extends or wraps FewShotRepository to support vector search/keywords mapping for few-shot prompt injection.
    Provides methods to dynamically add corrected query examples.
    """

    def __init__(self, repository: FewShotRepository | None = None) -> None:
        self.repository = repository or FewShotRepository()

    def select_few_shots(
        self,
        question: str,
        dialect: str = "",
        limit: int = 3,
        embedding_model: EmbeddingModel | None = None,
    ) -> list[FewShotExample]:
        """Retrieves matching few-shot examples using embeddings or keywords matching."""
        return self.repository.select_examples(question, dialect, limit, embedding_model)

    def add_example(
        self,
        question: str,
        sql: str,
        dialect: str = "",
        tags: list[str] | None = None,
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        """Dynamically adds a corrected/new example to the stored JSON file, embedding the prompt description."""
        examples = self.repository.load_examples()

        embedding = []
        if embedding_model:
            try:
                embedding = embedding_model.embed_text(question)
            except Exception:
                embedding = []

        new_example = FewShotExample(
            question=question,
            sql=sql,
            dialect=dialect,
            tags=tags or [],
            embedding=embedding
        )
        examples.append(new_example)
        self.repository.save_examples(examples)
