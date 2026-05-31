"""Tests for few-shot example persistence and selection."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.infrastructure.few_shot_repository import FewShotExample, FewShotRepository  # noqa: E402


class FixedEmbeddingModel:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed_text(self, text: str) -> list[float]:
        return self.vectors.get(text, [0.0, 0.0])


class FewShotRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "few_shot.json"
        self.repository = FewShotRepository(self.path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_save_and_load_examples(self) -> None:
        examples = [
            FewShotExample(
                question="Tổng doanh thu",
                sql="SELECT SUM(total) FROM orders;",
                dialect="MYSQL",
                tags=["doanh thu"],
                embedding=[1.0, 0.0],
            )
        ]

        self.repository.save_examples(examples)
        loaded = self.repository.load_examples()

        self.assertEqual(loaded, examples)

    def test_select_examples_by_embedding_when_available(self) -> None:
        self.repository.save_examples(
            [
                FewShotExample("Tên user", "SELECT full_name FROM users;", "MYSQL", embedding=[1.0, 0.0]),
                FewShotExample("Tổng đơn", "SELECT SUM(total) FROM orders;", "MYSQL", embedding=[0.0, 1.0]),
            ]
        )
        model = FixedEmbeddingModel({"Cho biết tên user": [1.0, 0.0]})

        selected = self.repository.select_examples("Cho biết tên user", "MYSQL", limit=1, embedding_model=model)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].question, "Tên user")

    def test_select_examples_falls_back_to_keywords_and_filters_dialect(self) -> None:
        self.repository.save_examples(
            [
                FewShotExample("Tổng doanh thu theo tháng", "SELECT SUM(total) FROM orders;", "MYSQL", tags=["doanh thu"]),
                FewShotExample("Tên user", "SELECT full_name FROM users;", "POSTGRESQL", tags=["user"]),
            ]
        )

        selected = self.repository.select_examples("doanh thu tháng", "MYSQL", limit=2)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].question, "Tổng doanh thu theo tháng")

    def test_empty_or_invalid_file_returns_empty_list(self) -> None:
        self.assertEqual(self.repository.load_examples(), [])
        self.path.write_text("{bad json", encoding="utf-8")
        self.assertEqual(self.repository.load_examples(), [])


if __name__ == "__main__":
    unittest.main()
