from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import pytest
from fpdf import FPDF

DIM = 384


class FakeEmbedder:
    """Makes repeatable vectors, so similar word sets land close together."""

    def _vector(self, text: str) -> list[float]:
        values = [0.0] * DIM
        for word in text.lower().replace("?", "").split():
            values[int(hashlib.sha256(word.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = sum(v * v for v in values) ** 0.5 or 1.0
        return [v / norm for v in values]

    async def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


def write_pdf(path: Path, pages: list[str]) -> Path:
    pdf = FPDF()
    pdf.set_font("helvetica", size=11)
    for text in pages:
        pdf.add_page()
        pdf.multi_cell(0, 6, text)
    pdf.output(str(path))
    return path
