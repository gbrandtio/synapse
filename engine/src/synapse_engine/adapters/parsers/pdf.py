"""Read PDFs in a separate process, so a corrupt file cannot take the engine down."""

from __future__ import annotations

import asyncio
import multiprocessing
from multiprocessing.connection import Connection
from pathlib import Path

import pypdfium2

from synapse_engine.domain.models import Page, UnreadableDocumentError

MAX_FILE_BYTES = 512 * 1024 * 1024
_TIME_LIMIT_SECONDS = 300


def extract_pages(path: Path) -> list[Page]:
    """Return the text of every page in a PDF."""
    document = pypdfium2.PdfDocument(str(path))
    try:
        pages = []
        for index in range(len(document)):
            text_page = document[index].get_textpage()
            pages.append(Page(index + 1, text_page.get_text_bounded().strip()))
        return pages
    finally:
        document.close()


def _worker(path: str, sender: Connection) -> None:
    try:
        pages = extract_pages(Path(path))
        sender.send([(page.number, page.text) for page in pages])
    except Exception as error:
        sender.send(error.__class__.__name__)
    finally:
        sender.close()


def _read_in_worker(path: Path, time_limit: float) -> list[Page]:
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(str(path), sender), daemon=True)
    process.start()
    sender.close()
    try:
        if not receiver.poll(time_limit):
            raise UnreadableDocumentError(f"Reading {path.name} took too long, so it was stopped.")
        try:
            result = receiver.recv()
        except EOFError as error:
            raise UnreadableDocumentError(f"{path.name} could not be read.") from error
    finally:
        process.kill()
        process.join()
        receiver.close()
    if isinstance(result, str):
        raise UnreadableDocumentError(f"{path.name} could not be read. It may be damaged.")
    return [Page(number, text) for number, text in result]


def _check_file(path: Path) -> None:
    if path.suffix.lower() != ".pdf":
        raise UnreadableDocumentError(f"{path.name} is not a PDF.")
    if not path.is_file() or path.is_symlink():
        raise UnreadableDocumentError(f"{path.name} could not be opened.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise UnreadableDocumentError(f"{path.name} is larger than the 512 MB limit.")


class PdfReader:
    """Reads PDF files. Pages with no text layer come back empty."""

    def __init__(self, time_limit: float = _TIME_LIMIT_SECONDS) -> None:
        self._time_limit = time_limit

    async def check(self, path: Path) -> None:
        """Raise UnreadableDocumentError if this file should not be opened at all."""
        await asyncio.to_thread(_check_file, path)

    async def read(self, path: Path) -> list[Page]:
        """Return the file's pages, or raise UnreadableDocumentError."""
        await self.check(path)
        return await asyncio.to_thread(_read_in_worker, path, self._time_limit)
