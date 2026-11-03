"""Add a document to the knowledge base."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from synapse_engine.application.ports import DocumentReader, Embedder, KnowledgeStore
from synapse_engine.domain.chunking import split_pages
from synapse_engine.domain.models import Document, UnreadableDocumentError

_EMBED_BATCH = 32


@dataclass(frozen=True, slots=True)
class IngestProgress:
    """Plain-language progress for the user."""

    message: str
    done: int = 0
    total: int = 0


@dataclass(frozen=True, slots=True)
class IngestFinished:
    """The document is ready to search."""

    document: Document
    already_present: bool


IngestEvent = IngestProgress | IngestFinished


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class IngestDocument:
    """Reads, splits and embeds a file, then publishes it in one step."""

    def __init__(self, reader: DocumentReader, embedder: Embedder, store: KnowledgeStore) -> None:
        self._reader = reader
        self._embedder = embedder
        self._store = store

    async def run(self, path: Path) -> AsyncIterator[IngestEvent]:
        """Add the file, yielding progress. Unchanged files are skipped."""
        name = path.name
        yield IngestProgress(f"Reading {name}")
        await self._reader.check(path)
        content_hash = await asyncio.to_thread(_hash_file, path)
        existing = await self._store.find_by_hash(content_hash)
        if existing is not None:
            yield IngestFinished(existing, already_present=True)
            return
        pages = await self._reader.read(path)
        passages = split_pages(name, pages)
        if not passages:
            raise UnreadableDocumentError(
                f"{name} has no readable text. It may be a scanned document."
            )
        vectors: list[list[float]] = []
        for start in range(0, len(passages), _EMBED_BATCH):
            batch = passages[start : start + _EMBED_BATCH]
            vectors.extend(await self._embedder.embed_passages([p.text for p in batch]))
            yield IngestProgress(f"Processing {name}", len(vectors), len(passages))
        document = await self._store.add_document(name, content_hash, len(pages), passages, vectors)
        yield IngestFinished(document, already_present=False)
