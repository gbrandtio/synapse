"""What the application needs from the outside world."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from synapse_engine.domain.models import Citation, Document, Page, Passage, SearchHit


class DocumentReader(Protocol):
    """Reads a file into pages of text."""

    async def check(self, path: Path) -> None:
        """Raise UnreadableDocumentError if this file should not be opened at all."""
        ...

    async def read(self, path: Path) -> list[Page]:
        """Return the file's pages, or raise UnreadableDocumentError."""
        ...


class Embedder(Protocol):
    """Turns text into vectors."""

    async def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one normalised vector per passage."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Return a normalised vector for a question."""
        ...


class KnowledgeStore(Protocol):
    """Stores documents and searches their passages."""

    async def find_by_hash(self, content_hash: str) -> Document | None:
        """Return the document with this content hash, if it is already stored."""
        ...

    async def add_document(
        self,
        name: str,
        content_hash: str,
        pages: int,
        passages: Sequence[Passage],
        vectors: Sequence[Sequence[float]],
    ) -> Document:
        """Store a document and all its passages in one transaction."""
        ...

    async def list_documents(self) -> list[Document]:
        """Return every stored document, newest first."""
        ...

    async def search(self, question: str, vector: Sequence[float], limit: int) -> list[SearchHit]:
        """Return the best passages for a question using hybrid search."""
        ...


@dataclass(frozen=True, slots=True)
class TokenEvent:
    """A piece of answer text."""

    text: str


@dataclass(frozen=True, slots=True)
class CitationsEvent:
    """The sources the finished answer relied on."""

    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class NotFoundEvent:
    """Nothing reliable was found, so no answer was attempted."""

    message: str


AnswerEvent = TokenEvent | CitationsEvent | NotFoundEvent


class Answerer(Protocol):
    """Answers a question from stored knowledge."""

    def answer(self, question: str) -> AsyncIterator[AnswerEvent]:
        """Stream the answer as events."""
        ...
