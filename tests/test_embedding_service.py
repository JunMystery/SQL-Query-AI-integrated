"""Tests for embedding abstraction and vector serialization."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.services.embedding_service import (  # noqa: E402
    DeterministicEmbeddingModel,
    SentenceTransformersEmbeddingModel,
    blob_to_vector,
    cosine_similarity,
    vector_to_blob,
)


class EmbeddingServiceTests(unittest.TestCase):
    def test_float32_vector_round_trip(self) -> None:
        vector = [0.25, -1.5, 3.0]

        restored = blob_to_vector(vector_to_blob(vector))

        self.assertEqual(len(restored), 3)
        self.assertAlmostEqual(restored[0], 0.25)
        self.assertAlmostEqual(restored[1], -1.5)
        self.assertAlmostEqual(restored[2], 3.0)

    def test_deterministic_embedding_is_stable(self) -> None:
        model = DeterministicEmbeddingModel(dimensions=8)

        first = model.embed_text("users full_name")
        second = model.embed_text("users full_name")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)

    def test_cosine_similarity_prefers_similar_vectors(self) -> None:
        self.assertGreater(cosine_similarity([1.0, 0.0], [0.8, 0.2]), 0.9)
        self.assertLess(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.1)

    def test_sentence_transformers_uses_default_lightweight_model_name(self) -> None:
        model = SentenceTransformersEmbeddingModel()

        self.assertEqual(model.model_name, "all-MiniLM-L6-v2")

    def test_sentence_transformers_adapter_uses_factory_lazily(self) -> None:
        calls: list[str] = []

        class FakeModel:
            def encode(self, text: str) -> list[float]:
                self.text = text
                return [1, 2.5, -3]

        def factory(model_name: str) -> FakeModel:
            calls.append(model_name)
            return FakeModel()

        model = SentenceTransformersEmbeddingModel(model_factory=factory)

        self.assertEqual(calls, [])
        self.assertEqual(model.embed_text("users"), [1.0, 2.5, -3.0])
        self.assertEqual(calls, ["all-MiniLM-L6-v2"])

    def test_sentence_transformers_adapter_has_clear_error_without_fallback(self) -> None:
        model = SentenceTransformersEmbeddingModel(model_factory=lambda _: (_ for _ in ()).throw(ImportError()))

        with self.assertRaisesRegex(RuntimeError, "sentence-transformers"):
            model.embed_text("users")

    def test_sentence_transformers_adapter_falls_back_when_model_unavailable(self) -> None:
        fallback = DeterministicEmbeddingModel(dimensions=8)
        model = SentenceTransformersEmbeddingModel(
            model_factory=lambda _: (_ for _ in ()).throw(RuntimeError("offline")),
            fallback_model=fallback,
        )

        self.assertEqual(model.embed_text("users"), fallback.embed_text("users"))


if __name__ == "__main__":
    unittest.main()
