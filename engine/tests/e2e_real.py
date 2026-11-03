"""Manual check with the real embedding model and bundled AI. Not part of the normal test run.

Run: uv run python tests/e2e_real.py <embedding dir> <ollama binary> <ollama models dir>
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path

from fpdf import FPDF
from langchain_ollama import ChatOllama

from synapse_engine.adapters.ai.ask_graph import GraphAnswerer
from synapse_engine.adapters.ai.embedder import FastEmbedEmbedder
from synapse_engine.adapters.ai.ollama_process import OllamaProcess
from synapse_engine.adapters.parsers.pdf import PdfReader
from synapse_engine.adapters.stores.sqlite_store import SqliteKnowledgeStore
from synapse_engine.application.ingest import IngestDocument, IngestFinished
from synapse_engine.application.ports import CitationsEvent, NotFoundEvent, TokenEvent

QUESTIONS = [
    "How long are backups kept?",
    "Which firmware fixes the PX-400 printer?",
    "How do I cancel the licence?",
    "What is the capital of Australia?",
]


async def main(embedding_dir: Path, binary: Path, models: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pdf = FPDF()
        pdf.set_font("helvetica", size=11)
        for text in [
            "Backups run nightly at 02:00 and are kept for 14 days. Restore from the Maintenance menu.",
            "The PX-400 label printer connects by USB. Firmware 2.1.7 fixes the buffer overflow.",
            "The licence renews every year. To cancel, contact sales at least 30 days before it expires.",
        ]:
            pdf.add_page()
            pdf.multi_cell(0, 6, text)
        pdf.output(str(root / "guide.pdf"))
        store = SqliteKnowledgeStore(root / "s.db")
        embedder = FastEmbedEmbedder(embedding_dir, local_only=False)
        started = time.perf_counter()
        async for event in IngestDocument(PdfReader(), embedder, store).run(root / "guide.pdf"):
            if isinstance(event, IngestFinished):
                print("ingested", event.document, f"{time.perf_counter() - started:.1f}s")
        ollama = OllamaProcess(binary, models)

        async def model() -> ChatOllama:
            return ChatOllama(
                base_url=await ollama.ensure_started(),
                model="gemma3:1b",
                temperature=0.2,
                num_predict=200,
                reasoning=False,
            )

        answerer = GraphAnswerer(embedder, store, model)
        try:
            for question in QUESTIONS:
                started = time.perf_counter()
                first = None
                text = ""
                async for event in answerer.answer(question):
                    if isinstance(event, TokenEvent):
                        first = first or time.perf_counter() - started
                        text += event.text
                    elif isinstance(event, CitationsEvent):
                        print(
                            f"Q: {question}\nA: {text.strip()}\n   sources: {[(c.number, c.document_name, c.page) for c in event.citations]} first token {first:.1f}s total {time.perf_counter() - started:.1f}s"
                        )
                    elif isinstance(event, NotFoundEvent):
                        print(
                            f"Q: {question}\nA: [not found] {event.message} ({time.perf_counter() - started:.2f}s)"
                        )
        finally:
            ollama.stop()


if __name__ == "__main__":
    asyncio.run(main(*(Path(a) for a in sys.argv[1:4])))
