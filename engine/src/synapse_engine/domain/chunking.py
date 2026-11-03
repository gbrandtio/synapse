"""Split pages into passages. Sizes count words, as a stand-in for tokens."""

from __future__ import annotations

from collections.abc import Iterable

from synapse_engine.domain.models import Page, Passage

PASSAGE_WORDS = 375  # About 500 tokens.
OVERLAP_WORDS = 45  # About 60 tokens.


def split_pages(
    document_name: str,
    pages: Iterable[Page],
    passage_words: int = PASSAGE_WORDS,
    overlap_words: int = OVERLAP_WORDS,
) -> list[Passage]:
    """Split each page into overlapping passages, keeping the page number."""
    if not 0 <= overlap_words < passage_words:
        raise ValueError("overlap_words must be at least 0 and below passage_words")
    step = passage_words - overlap_words
    passages: list[Passage] = []
    for page in pages:
        words = page.text.split()
        for start in range(0, len(words), step):
            piece = words[start : start + passage_words]
            passages.append(Passage(document_name, page.number, " ".join(piece)))
            if start + passage_words >= len(words):
                break
    return passages
