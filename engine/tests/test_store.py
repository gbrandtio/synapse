from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from synapse_engine.adapters.stores.sqlite_store import KEYWORD_SQL, SqliteKnowledgeStore
from synapse_engine.domain.models import Passage
from tests.conftest import FakeEmbedder


async def add(store: SqliteKnowledgeStore, embedder: FakeEmbedder, name: str, texts: list[str]):
    passages = [Passage(name, i + 1, t) for i, t in enumerate(texts)]
    vectors = await embedder.embed_passages(texts)
    return await store.add_document(name, f"hash-{name}", len(texts), passages, vectors)


@pytest.fixture
def store(tmp_path: Path) -> SqliteKnowledgeStore:
    return SqliteKnowledgeStore(tmp_path / "data" / "s.db")


async def test_finds_passage_by_meaning_vector(store, embedder) -> None:
    await add(store, embedder, "a.pdf", ["backups are kept for fourteen days", "printers use usb"])
    question = "backups are kept for how many days"
    hits = await store.search(question, await embedder.embed_query(question), 2)
    assert hits[0].passage.text.startswith("backups")
    assert hits[0].passage.document_name == "a.pdf"
    assert hits[0].passage.page == 1
    assert hits[0].similarity > hits[1].similarity


async def test_exact_term_outranks_vector_only_results(store, embedder) -> None:
    texts = [f"ordinary passage number {i} about nothing" for i in range(30)]
    texts.append("gateway returned ERR_TIMEOUT_504 overnight")
    await add(store, embedder, "a.pdf", texts)
    hits = await store.search("ERR_TIMEOUT_504", await embedder.embed_query("unrelated words"), 3)
    assert "ERR_TIMEOUT_504" in hits[0].passage.text


async def test_punctuation_only_question_returns_nothing(store, embedder) -> None:
    await add(store, embedder, "a.pdf", ["alpha"])
    assert await store.search("???", await embedder.embed_query("x"), 3) == []


async def test_search_operators_in_a_question_do_not_raise(store, embedder) -> None:
    await add(store, embedder, "a.pdf", ["alpha"])
    for question in ['"unbalanced', "NEAR(a b", "a AND", "col:alpha", "*"]:
        await store.search(question, await embedder.embed_query(question), 3)


async def test_duplicate_hash_is_found_and_listed_once(store, embedder) -> None:
    created = await add(store, embedder, "a.pdf", ["alpha", "beta"])
    assert created.passages == 2
    assert await store.find_by_hash("hash-a.pdf") == created
    assert await store.find_by_hash("other") is None
    assert await store.list_documents() == [created]


async def test_failed_write_leaves_nothing_behind(store) -> None:
    with pytest.raises(ValueError, match="one vector"):
        await store.add_document("a", "h", 1, [Passage("a", 1, "x")], [])
    bad_vector = [[0.1, 0.2]]  # Wrong size, so sqlite-vec refuses it inside the transaction.
    with pytest.raises(sqlite3.Error):
        await store.add_document("a", "h", 1, [Passage("a", 1, "x")], bad_vector)
    assert await store.list_documents() == []
    assert await store.search("x", [0.0] * 384, 3) == []


def test_keyword_filter_never_uses_the_slow_form() -> None:
    assert "rowid in" not in KEYWORD_SQL.lower()
