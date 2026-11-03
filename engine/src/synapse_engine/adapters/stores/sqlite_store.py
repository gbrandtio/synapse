"""One SQLite file holds documents, passages, vectors and keywords. See ADR 0015."""

from __future__ import annotations

import asyncio
import sqlite3
import struct
from collections.abc import Sequence
from pathlib import Path

import sqlite_vec

from synapse_engine.domain.models import Document, Passage, SearchHit
from synapse_engine.domain.search_rules import keyword_weight, to_fts_query

EMBEDDING_DIM = 384
_RRF_K = 60
_CANDIDATES = 40

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS document(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  content_hash TEXT NOT NULL UNIQUE,
  pages INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS passage(
  id INTEGER PRIMARY KEY,
  document_id INTEGER NOT NULL REFERENCES document(id) ON DELETE CASCADE,
  page INTEGER NOT NULL,
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS passage_document ON passage(document_id);
CREATE VIRTUAL TABLE IF NOT EXISTS passage_vec USING vec0(
  id INTEGER PRIMARY KEY,
  embedding FLOAT[{EMBEDDING_DIM}] distance_metric=cosine
);
CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts USING fts5(
  text, content='passage', content_rowid='id', tokenize='unicode61'
);
"""

# Filters on this query must use a join. `rowid IN (subquery)` took 1.6 s at 100,000 passages
# in Phase 0, against 1 to 12 ms for a join.
KEYWORD_SQL = """
SELECT id, row_number() OVER (ORDER BY score) AS rank_position FROM (
  SELECT f.rowid AS id, f.rank AS score FROM passage_fts f JOIN passage p ON p.id = f.rowid
  WHERE passage_fts MATCH :terms ORDER BY f.rank LIMIT :candidates
)
"""
VECTOR_SQL = """
SELECT id, distance, row_number() OVER (ORDER BY distance) AS rank_position FROM passage_vec
WHERE embedding MATCH :vector AND k = :candidates
"""
HYBRID_SQL = f"""
WITH v AS ({VECTOR_SQL}), k AS ({KEYWORD_SQL}),
merged AS (
  SELECT id, sum(score) AS score FROM (
    SELECT id, 1.0 / (:rrf_k + rank_position) AS score FROM v
    UNION ALL
    SELECT id, :keyword_weight / (:rrf_k + rank_position) FROM k
  ) GROUP BY id
)
SELECT d.name, p.page, p.text, 1.0 - coalesce(v.distance, 1.0) AS similarity,
  k.rank_position IS 1 AS is_top_keyword_match
FROM merged m
JOIN passage p ON p.id = m.id
JOIN document d ON d.id = p.document_id
LEFT JOIN v ON v.id = m.id
LEFT JOIN k ON k.id = m.id
ORDER BY m.score DESC LIMIT :limit
"""  # noqa: S608 - joins constants, values are bound


def _pack(vector: Sequence[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


class SqliteKnowledgeStore:
    """Keeps all knowledge in one SQLite file, using one short connection per operation."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            connection.executescript(_SCHEMA)
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.enable_load_extension(True)
        sqlite_vec.load(connection)
        connection.enable_load_extension(False)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _find_by_hash(self, content_hash: str) -> Document | None:
        connection = self._connect()
        try:
            row = connection.execute(
                """SELECT d.id, d.name, d.pages, count(p.id) FROM document d
                   LEFT JOIN passage p ON p.document_id = d.id
                   WHERE d.content_hash = ? GROUP BY d.id""",
                (content_hash,),
            ).fetchone()
        finally:
            connection.close()
        return Document(*row) if row else None

    async def find_by_hash(self, content_hash: str) -> Document | None:
        """Return the document with this content hash, if it is already stored."""
        return await asyncio.to_thread(self._find_by_hash, content_hash)

    def _add_document(
        self,
        name: str,
        content_hash: str,
        pages: int,
        passages: Sequence[Passage],
        vectors: Sequence[Sequence[float]],
    ) -> Document:
        if len(passages) != len(vectors):
            raise ValueError("Each passage needs exactly one vector")
        connection = self._connect()
        try:
            with connection:
                cursor = connection.execute(
                    "INSERT INTO document(name, content_hash, pages) VALUES (?, ?, ?)",
                    (name, content_hash, pages),
                )
                document_id = int(cursor.lastrowid or 0)
                for passage, vector in zip(passages, vectors, strict=True):
                    row = connection.execute(
                        "INSERT INTO passage(document_id, page, text) VALUES (?, ?, ?)",
                        (document_id, passage.page, passage.text),
                    )
                    connection.execute(
                        "INSERT INTO passage_vec(id, embedding) VALUES (?, ?)",
                        (row.lastrowid, _pack(vector)),
                    )
                    connection.execute(
                        "INSERT INTO passage_fts(rowid, text) VALUES (?, ?)",
                        (row.lastrowid, passage.text),
                    )
        finally:
            connection.close()
        return Document(document_id, name, pages, len(passages))

    async def add_document(
        self,
        name: str,
        content_hash: str,
        pages: int,
        passages: Sequence[Passage],
        vectors: Sequence[Sequence[float]],
    ) -> Document:
        """Store a document and all its passages in one transaction."""
        return await asyncio.to_thread(
            self._add_document, name, content_hash, pages, passages, vectors
        )

    def _list_documents(self) -> list[Document]:
        connection = self._connect()
        try:
            rows = connection.execute(
                """SELECT d.id, d.name, d.pages, count(p.id) FROM document d
                   LEFT JOIN passage p ON p.document_id = d.id
                   GROUP BY d.id ORDER BY d.id DESC"""
            ).fetchall()
        finally:
            connection.close()
        return [Document(*row) for row in rows]

    async def list_documents(self) -> list[Document]:
        """Return every stored document, newest first."""
        return await asyncio.to_thread(self._list_documents)

    def _search(self, question: str, vector: Sequence[float], limit: int) -> list[SearchHit]:
        terms = to_fts_query(question)
        if not terms:
            return []
        connection = self._connect()
        try:
            rows = connection.execute(
                HYBRID_SQL,
                {
                    "vector": _pack(vector),
                    "terms": terms,
                    "candidates": _CANDIDATES,
                    "rrf_k": _RRF_K,
                    "keyword_weight": keyword_weight(question),
                    "limit": limit,
                },
            ).fetchall()
        finally:
            connection.close()
        return [
            SearchHit(Passage(name, page, text), float(similarity), bool(is_top))
            for name, page, text, similarity, is_top in rows
        ]

    async def search(self, question: str, vector: Sequence[float], limit: int) -> list[SearchHit]:
        """Return the best passages for a question using hybrid search."""
        return await asyncio.to_thread(self._search, question, vector, limit)
