"""Local text embeddings with fastembed, loaded once per process."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, Protocol

from app.config import settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding

EmbedderState = Literal["ready", "loading", "not_loaded"]


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


def check_dim(vectors: list[list[float]]) -> list[list[float]]:
    for vector in vectors:
        if len(vector) != settings.embedding_dim:
            raise ValueError(
                f"Embedding has {len(vector)} dimensions, "
                f"EMBEDDING_DIM is {settings.embedding_dim}"
            )
    return vectors


class FastEmbedder:
    """fastembed wrapper; the model loads lazily and inference runs in a thread."""

    def __init__(
        self,
        model_name: str = settings.embedding_model,
        cache_dir: str = settings.embedding_cache_dir,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model: TextEmbedding | None = None
        self._loading = False
        self._lock = threading.Lock()

    @property
    def state(self) -> EmbedderState:
        if self._model is not None:
            return "ready"
        return "loading" if self._loading else "not_loaded"

    def _load(self) -> TextEmbedding:
        with self._lock:
            if self._model is None:
                self._loading = True
                try:
                    from fastembed import TextEmbedding

                    self._model = TextEmbedding(
                        self.model_name, cache_dir=self.cache_dir
                    )
                finally:
                    self._loading = False
            return self._model

    def _embed_sync(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load()
        return check_dim([vector.tolist() for vector in model.embed(list(texts))])

    def _embed_query_sync(self, text: str) -> list[float]:
        model = self._load()
        return check_dim([vector.tolist() for vector in model.query_embed(text)])[0]

    async def warm_up(self) -> None:
        await asyncio.to_thread(self._embed_sync, ["Warm-up"])

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_sync, texts)

    async def embed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._embed_query_sync, text)


_embedder: FastEmbedder | None = None


def get_embedder_state() -> EmbedderState:
    """Inspect the model without creating it or waiting for its loading lock."""
    return _embedder.state if _embedder is not None else "not_loaded"


def get_embedder() -> FastEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = FastEmbedder()
    return _embedder
