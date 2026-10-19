"""Эмбеддинги. Два провайдера: локальный (fastembed, бесплатно и без лимитов) и OpenAI-совместимый API."""
import math
from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class LocalEmbedder:
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding  # тяжёлый импорт — только когда реально нужен

        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_normalize(v.tolist()) for v in self._model.embed(texts)]


class ApiEmbedder:
    def __init__(self, base_url: str, api_key: str, model: str, dim: int):
        from openai import OpenAI

        self._client = OpenAI(base_url=base_url, api_key=api_key, max_retries=3)
        self._model = model
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            resp = self._client.embeddings.create(model=self._model, input=texts[i : i + 64], dimensions=self._dim)
            out.extend(_normalize(d.embedding) for d in resp.data)
        return out


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embeddings_provider == "api":
        return ApiEmbedder(
            s.embeddings_base_url or s.llm_base_url,
            s.embeddings_api_key or s.llm_api_key,
            s.embedding_model,
            s.embedding_dim,
        )
    return LocalEmbedder(s.embedding_model)
