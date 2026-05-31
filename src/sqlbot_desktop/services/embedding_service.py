"""Embedding abstractions used by schema linking."""

from __future__ import annotations

from array import array
import hashlib
import math
import re
from typing import Protocol


class EmbeddingModel(Protocol):
    """Minimal embedding interface."""

    def embed_text(self, text: str) -> list[float]:
        """Return a vector representation for text."""


class DeterministicEmbeddingModel:
    """Small local embedding fallback for tests and offline startup."""

    def __init__(self, dimensions: int = 64) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[\w]+", text.lower(), flags=re.UNICODE)
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        return normalize_vector(vector)


class SentenceTransformersEmbeddingModel:
    """Optional sentence-transformers adapter loaded lazily."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None

    def embed_text(self, text: str) -> list[float]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        vector = self._model.encode(text)
        return [float(value) for value in vector]


def vector_to_blob(vector: list[float]) -> bytes:
    values = array("f", [float(value) for value in vector])
    if values.itemsize != 4:
        raise RuntimeError("float32 array support is required")
    return values.tobytes()


def blob_to_vector(blob: bytes | None) -> list[float]:
    if not blob:
        return []
    values = array("f")
    values.frombytes(blob)
    return [float(value) for value in values]


def normalize_vector(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return [0.0 for _ in vector]
    return [value / magnitude for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = normalize_vector(left)
    right_norm = normalize_vector(right)
    return sum(a * b for a, b in zip(left_norm, right_norm))
