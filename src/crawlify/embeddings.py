from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: List[List[float]]
    model: str


class EmbeddingProvider:
    def embed(self, texts: Iterable[str]) -> EmbeddingResult:
        raise NotImplementedError


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "sentence-transformers not installed. Install to use this provider."
            ) from exc
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: Iterable[str]) -> EmbeddingResult:
        text_list = list(texts)
        vectors = self._model.encode(text_list, normalize_embeddings=True).tolist()
        return EmbeddingResult(vectors=vectors, model=self.model_name)
