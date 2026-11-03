"""Local embeddings through FastEmbed. The model must already be on disk."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed import TextEmbedding

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
_THREADS = 4


class FastEmbedEmbedder:
    """Loads the model on first use, because it is slow to import."""

    def __init__(self, cache_dir: Path, local_only: bool = True) -> None:
        self._cache_dir = cache_dir
        self._local_only = local_only
        self._model: TextEmbedding | None = None
        self._lock = Lock()

    def _load(self) -> TextEmbedding:
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(
                    EMBEDDING_MODEL,
                    cache_dir=str(self._cache_dir),
                    threads=_THREADS,
                    local_files_only=self._local_only,
                )
            return self._model

    def _embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._load().passage_embed(list(texts))]

    def _embed_query(self, text: str) -> list[float]:
        return [float(x) for x in next(iter(self._load().query_embed(text)))]

    async def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one normalised vector per passage."""
        return await asyncio.to_thread(self._embed_passages, texts)

    async def embed_query(self, text: str) -> list[float]:
        """Return a normalised vector for a question."""
        return await asyncio.to_thread(self._embed_query, text)
