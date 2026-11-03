"""Does keyword search earn its place? Adds exact-term questions and tries weighted fusion.

Exact-term questions name an identifier or code taken from the indexed text. The other
sets are the same as bench_retrieval.py. Only the likely default embedding model is used.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

from bench_retrieval import BM25, CACHE, CANDIDATES, TOP_K, code_corpus, metrics, prose_corpus
from data.prose_queries import PROSE_QUERIES
from data.tickets import TICKET_QUERIES, TICKETS

ROOT = Path(__file__).parent
MODEL = "BAAI/bge-small-en-v1.5"
RERANK = "Xenova/ms-marco-MiniLM-L-6-v2"


def exact_queries(code_docs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The bare name of a function that appears in exactly one indexed passage."""
    defs: list[tuple[str, str]] = []
    for pid, text in code_docs:
        m = re.search(r"def (\w+)\(", text)
        if m:
            defs.append((m.group(1), pid))
    out = []
    for name, pid in defs:
        hits = [p for p, t in code_docs if name in t]
        if hits == [pid] and "_" in name:
            out.append((name, pid))
    return out


EXACT_TICKETS = [
    ("ERR_TIMEOUT_504", "T3"), ("PX-400", "T11"), ("CustomerController.getById", "T19"),
    ("max_connections", "T3"), ("client_max_body_size", "T14"), ("UploadActivity", "T6"),
    ("migration 0042", "T23"), ("firmware 2.1.7", "T11"), ("SameSite=None", "T1"), ("project.owner_id", "T5"),
]


def fuse(vr: np.ndarray, kr: np.ndarray, kw: float, k: int = 60) -> np.ndarray:
    s = np.zeros(len(vr))
    for rank, i in enumerate(vr):
        s[i] += 1.0 / (k + rank + 1)
    for rank, i in enumerate(kr):
        s[i] += kw / (k + rank + 1)
    return np.argsort(-s)


def main() -> None:
    code_docs, code_q = code_corpus()
    docs = code_docs + prose_corpus() + TICKETS
    ids = [d[0] for d in docs]
    texts = [d[1] for d in docs]
    sets = {
        "code_meaning": code_q,
        "prose": PROSE_QUERIES,
        "tickets": TICKET_QUERIES,
        "exact_code": exact_queries(code_docs),
        "exact_tickets": EXACT_TICKETS,
    }
    print({k: len(v) for k, v in sets.items()}, flush=True)
    model = TextEmbedding(MODEL, cache_dir=CACHE, threads=4)
    E = np.array(list(model.passage_embed(texts, batch_size=16)), dtype=np.float32)
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    bm = BM25(texts)
    rr = TextCrossEncoder(RERANK, cache_dir=CACHE, threads=4)
    results: dict[str, dict[str, object]] = {}
    for name, qs in sets.items():
        qt = [q for q, _ in qs]
        exp = [e for _, e in qs]
        Q = np.array(list(model.query_embed(qt)), dtype=np.float32)
        Q /= np.linalg.norm(Q, axis=1, keepdims=True)
        vrs = [np.argsort(-(E @ Q[i])) for i in range(len(qt))]
        krs = [np.argsort(-bm.scores(q)) for q in qt]
        row: dict[str, object] = {"n": len(qs)}
        row["vector"] = metrics([[ids[j] for j in v[:CANDIDATES]] for v in vrs], exp)["recall@6"]
        row["keyword"] = metrics([[ids[j] for j in k[:CANDIDATES]] for k in krs], exp)["recall@6"]
        for w in (0.1, 0.25, 0.5, 1.0):
            row[f"rrf_kw{w}"] = metrics([[ids[j] for j in fuse(v, k, w)[:CANDIDATES]] for v, k in zip(vrs, krs)], exp)["recall@6"]
        # Re-rank few candidates, which is cheaper than the planned 40.
        for w, cand in ((0.25, 12), (0.25, 20)):
            ranked = []
            for q, v, k in zip(qt, vrs, krs):
                top = fuse(v, k, w)[:cand]
                scores = np.array(list(rr.rerank(q, [texts[j] for j in top], batch_size=8)))
                ranked.append([ids[top[j]] for j in np.argsort(-scores)])
            row[f"rerank_top{cand}_kw{w}"] = metrics(ranked, exp)["recall@6"]
        results[name] = row
        print(name, json.dumps(row), flush=True)
    (ROOT / "results" / "weights.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    assert TOP_K == 6
    main()
