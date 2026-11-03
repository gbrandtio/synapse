"""Core types. This module imports no frameworks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Page:
    """The text of one page of a document."""

    number: int
    text: str


@dataclass(frozen=True, slots=True)
class Passage:
    """One searchable piece of a document."""

    document_name: str
    page: int
    text: str


@dataclass(frozen=True, slots=True)
class Document:
    """A document stored in the knowledge base."""

    id: int
    name: str
    pages: int
    passages: int


@dataclass(frozen=True, slots=True)
class Citation:
    """A numbered source. `is_inferred` means the AI did not cite it, so the app added it."""

    number: int
    document_name: str
    page: int
    text: str
    is_inferred: bool = False


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A passage found by search, with how close its meaning is to the question."""

    passage: Passage
    similarity: float
    is_top_keyword_match: bool = False


class UnreadableDocumentError(Exception):
    """A document could not be read. The message is safe to show the user."""
