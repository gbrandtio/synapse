from __future__ import annotations

import pytest

from synapse_engine.domain.chunking import split_pages
from synapse_engine.domain.models import Page
from synapse_engine.domain.search_rules import (
    EXACT_KEYWORD_WEIGHT,
    LIGHT_KEYWORD_WEIGHT,
    keyword_weight,
    to_fts_query,
)


def test_short_page_is_one_passage_with_its_page_number() -> None:
    passages = split_pages("a.pdf", [Page(3, "hello world")])
    assert [(p.document_name, p.page, p.text) for p in passages] == [("a.pdf", 3, "hello world")]


def test_long_page_overlaps_and_loses_no_words() -> None:
    words = [f"w{i}" for i in range(25)]
    passages = split_pages("a", [Page(1, " ".join(words))], passage_words=10, overlap_words=2)
    assert passages[0].text.split()[-2:] == passages[1].text.split()[:2]
    assert {w for p in passages for w in p.text.split()} == set(words)
    assert passages[-1].text.split()[-1] == "w24"


def test_text_ending_exactly_on_a_boundary_adds_no_empty_passage() -> None:
    passages = split_pages("a", [Page(1, " ".join("x" * 10))], passage_words=10, overlap_words=2)
    assert len(passages) == 1


def test_empty_page_gives_no_passages() -> None:
    assert split_pages("a", [Page(1, "   ")]) == []


def test_invalid_overlap_is_rejected() -> None:
    with pytest.raises(ValueError, match="overlap"):
        split_pages("a", [], passage_words=5, overlap_words=5)


@pytest.mark.parametrize(
    "question",
    ["ERR_TIMEOUT_504", "PX-400", "getUserById", "firmware 2.1.7", "CustomerController.getById"],
)
def test_exact_terms_get_a_heavy_keyword_weight(question: str) -> None:
    assert keyword_weight(question) == EXACT_KEYWORD_WEIGHT


@pytest.mark.parametrize(
    "question", ["How long are backups kept?", "why did the PX-400 printer stop responding today"]
)
def test_ordinary_questions_get_a_light_keyword_weight(question: str) -> None:
    assert keyword_weight(question) == LIGHT_KEYWORD_WEIGHT


def test_fts_query_quotes_words_so_operators_are_harmless() -> None:
    assert to_fts_query('NOT "a" OR b*') == '"NOT" OR "a" OR "OR" OR "b"'
    assert to_fts_query("?!") == ""
