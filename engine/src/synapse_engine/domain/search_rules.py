"""Search rules chosen from Phase 0 measurements. See ADR 0016."""

from __future__ import annotations

import re

LIGHT_KEYWORD_WEIGHT = 0.1
EXACT_KEYWORD_WEIGHT = 1.0
_MAX_EXACT_WORDS = 3
_EXACT_TERM = re.compile(r"\w+[_.=-]\w+|[a-z]+[A-Z]\w*|[A-Z]{2,}\w*\d|\b\d[\d.]{2,}\b")
_WORD = re.compile(r"\w+", re.UNICODE)


def keyword_weight(question: str) -> float:
    """Return a higher keyword weight when a short question looks like an exact term."""
    is_short = len(question.split()) <= _MAX_EXACT_WORDS
    return (
        EXACT_KEYWORD_WEIGHT if is_short and _EXACT_TERM.search(question) else LIGHT_KEYWORD_WEIGHT
    )


def to_fts_query(question: str) -> str:
    """Turn a question into an FTS5 query, quoting each word so nothing acts as an operator."""
    return " OR ".join(f'"{word}"' for word in _WORD.findall(question))
