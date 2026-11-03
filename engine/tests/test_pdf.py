from __future__ import annotations

import pytest

from synapse_engine.adapters.parsers.pdf import PdfReader, _read_in_worker
from synapse_engine.domain.models import UnreadableDocumentError
from tests.conftest import write_pdf


async def test_reads_each_page_in_a_worker(tmp_path) -> None:
    path = write_pdf(tmp_path / "a.pdf", ["first page text", "second page text"])
    pages = await PdfReader().read(path)
    assert [(p.number, p.text) for p in pages] == [(1, "first page text"), (2, "second page text")]


async def test_corrupt_pdf_gives_a_friendly_error(tmp_path) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"this is not a pdf")
    with pytest.raises(UnreadableDocumentError, match="damaged"):
        await PdfReader().read(path)


async def test_other_file_types_are_refused(tmp_path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("x")
    with pytest.raises(UnreadableDocumentError, match="not a PDF"):
        await PdfReader().read(path)


async def test_missing_file_is_refused(tmp_path) -> None:
    with pytest.raises(UnreadableDocumentError, match="could not be opened"):
        await PdfReader().read(tmp_path / "gone.pdf")


async def test_symlink_is_refused(tmp_path) -> None:
    target = write_pdf(tmp_path / "real.pdf", ["x"])
    link = tmp_path / "link.pdf"
    link.symlink_to(target)
    with pytest.raises(UnreadableDocumentError, match="could not be opened"):
        await PdfReader().read(link)


def test_time_limit_stops_the_worker(tmp_path) -> None:
    path = write_pdf(tmp_path / "a.pdf", ["x"])
    with pytest.raises(UnreadableDocumentError, match="too long"):
        _read_in_worker(path, time_limit=0)
