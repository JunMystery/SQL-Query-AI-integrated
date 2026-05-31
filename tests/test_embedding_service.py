"""Tests for embedding abstraction and vector serialization."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlbot_desktop.services.embedding_service import (  # noqa: E402
    DeterministicEmbeddingModel,
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


if __name__ == "__main__":
    unittest.main()
