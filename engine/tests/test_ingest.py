from __future__ import annotations

import pytest

from synapse_engine.adapters.parsers.pdf import PdfReader
from synapse_engine.adapters.stores.sqlite_store import SqliteKnowledgeStore
from synapse_engine.application.ingest import IngestDocument, IngestFinished, IngestProgress
from synapse_engine.domain.models import UnreadableDocumentError
from tests.conftest import write_pdf


async def collect(ingest, path):
    return [event async for event in ingest.run(path)]


@pytest.fixture
def ingest(tmp_path, embedder):
    return IngestDocument(PdfReader(), embedder, SqliteKnowledgeStore(tmp_path / "s.db"))


async def test_adds_a_pdf_with_progress(ingest, tmp_path) -> None:
    events = await collect(ingest, write_pdf(tmp_path / "a.pdf", ["alpha", "beta"]))
    assert isinstance(events[0], IngestProgress)
    assert (events[-2].done, events[-2].total) == (2, 2)
    final = events[-1]
    assert isinstance(final, IngestFinished)
    assert not final.already_present
    assert (final.document.name, final.document.pages, final.document.passages) == ("a.pdf", 2, 2)


async def test_same_file_twice_is_skipped(ingest, tmp_path) -> None:
    path = write_pdf(tmp_path / "a.pdf", ["alpha"])
    first = (await collect(ingest, path))[-1]
    second = (await collect(ingest, path))[-1]
    assert second.already_present
    assert second.document == first.document


async def test_other_file_types_are_refused_before_being_read(tmp_path, embedder) -> None:
    class NoHashing(PdfReader):
        async def read(self, path):
            raise AssertionError("must not read")

    path = tmp_path / "huge.bin"
    path.write_bytes(b"x")
    ingest = IngestDocument(NoHashing(), embedder, SqliteKnowledgeStore(tmp_path / "s.db"))
    with pytest.raises(UnreadableDocumentError, match="not a PDF"):
        await collect(ingest, path)


async def test_pdf_with_no_text_explains_why(ingest, tmp_path) -> None:
    path = write_pdf(tmp_path / "blank.pdf", [""])
    with pytest.raises(UnreadableDocumentError, match="scanned"):
        await collect(ingest, path)
