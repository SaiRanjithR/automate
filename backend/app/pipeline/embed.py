"""Text embeddings. `fastembed` (ONNX bge-small, local) or a dependency-free hashing embedder."""

import hashlib
import itertools
import logging
import math
import threading
from collections import Counter
from functools import lru_cache
from typing import Protocol

import numpy as np
import numpy.typing as npt

from app.core.config import Settings
from app.pipeline.textutil import words

logger = logging.getLogger(__name__)
Vector = npt.NDArray[np.float32]


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> Vector: ...


class HashEmbedder:
    """Feature-hashing of word unigrams + bigrams with sublinear TF. Lexical, fast, offline."""

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim
        self.name = f"hash-{dim}"

    def _index(self, token: str) -> int:
        return (
            int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "little")
            % self.dim
        )

    def embed(self, texts: list[str]) -> Vector:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            tokens = [w for w in words(text) if len(w) > 2 or w[0].isdigit()]
            grams = [*tokens, *(f"{a}_{b}" for a, b in itertools.pairwise(tokens))]
            for token, count in Counter(grams).items():
                out[row, self._index(token)] += 1.0 + math.log(count)
            norm = float(np.linalg.norm(out[row]))
            if norm:
                out[row] /= norm
        return out


class FastEmbedder:
    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        self._lock = threading.Lock()
        probe = next(iter(self._model.embed(["probe"])))
        self.dim = len(probe)
        self.name = f"fastembed-{model_name}"

    def embed(self, texts: list[str]) -> Vector:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        with self._lock:
            vectors = np.array(list(self._model.embed(texts, batch_size=32)), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms


@lru_cache(maxsize=4)
def _cached_embedder(provider: str, model: str) -> Embedder:
    if provider == "fastembed":
        try:
            return FastEmbedder(model)
        except Exception:
            logger.warning(
                "fastembed model %s unavailable; falling back to hashing embedder", model
            )
    return HashEmbedder()


def get_embedder(settings: Settings) -> Embedder:
    return _cached_embedder(settings.embedding_provider, settings.embedding_model)


def to_bytes(vector: Vector) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def from_bytes(blob: bytes) -> Vector:
    return np.frombuffer(blob, dtype=np.float32)
