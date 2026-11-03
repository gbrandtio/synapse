"""Try one rule: a light keyword weight, raised when the question looks like an exact term."""
from __future__ import annotations
import json, re
from pathlib import Path
import numpy as np
from fastembed import TextEmbedding
from bench_retrieval import BM25, CACHE, CANDIDATES, code_corpus, metrics, prose_corpus
from bench_weights import EXACT_TICKETS, MODEL, exact_queries, fuse
from data.prose_queries import PROSE_QUERIES
from data.tickets import TICKET_QUERIES, TICKETS

IDENT = re.compile(r"\w+[_.=-]\w+|[a-z]+[A-Z]\w*|[A-Z]{2,}\w*\d|\b\d[\d.]{2,}\b")

def looks_exact(q: str) -> bool:
    return len(q.split()) <= 3 and bool(IDENT.search(q))

code_docs, code_q = code_corpus()
docs = code_docs + prose_corpus() + TICKETS
ids = [d[0] for d in docs]; texts = [d[1] for d in docs]
sets = {"code_meaning": code_q, "prose": PROSE_QUERIES, "tickets": TICKET_QUERIES, "exact_code": exact_queries(code_docs), "exact_tickets": EXACT_TICKETS}
m = TextEmbedding(MODEL, cache_dir=CACHE, threads=4)
E = np.array(list(m.passage_embed(texts, batch_size=16)), dtype=np.float32); E /= np.linalg.norm(E, axis=1, keepdims=True)
bm = BM25(texts); out = {}
for name, qs in sets.items():
    qt = [q for q, _ in qs]; exp = [e for _, e in qs]
    Q = np.array(list(m.query_embed(qt)), dtype=np.float32); Q /= np.linalg.norm(Q, axis=1, keepdims=True)
    ranked = []; flagged = 0
    for i, q in enumerate(qt):
        w = 1.0 if looks_exact(q) else 0.1
        flagged += w == 1.0
        ranked.append([ids[j] for j in fuse(np.argsort(-(E @ Q[i])), np.argsort(-bm.scores(q)), w)[:CANDIDATES]])
    out[name] = {**metrics(ranked, exp), "flagged_exact": flagged}
    print(name, out[name], flush=True)
Path("results/adaptive.json").write_text(json.dumps(out, indent=1))
