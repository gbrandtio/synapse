"""Phase 0 tests 2 and 3: which local models, and does the pipeline beat naive RAG?

The test set is small and partly hand-written, so read the results as a screen,
not as a precise ranking. Code queries come from standard-library docstrings, with
the docstring removed from the indexed code. Prose comes from this repo's docs.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

from data.prose_queries import PROSE_QUERIES
from data.tickets import TICKET_QUERIES, TICKETS

ROOT = Path(__file__).parent
CACHE = str(ROOT / ".cache" / "fastembed")
TOP_K = 6
CANDIDATES = 40


def code_corpus(limit: int = 300) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (docs, queries), taking functions with a docstring from the stdlib."""
    lib = Path(ast.__file__).parent
    docs: list[tuple[str, str]] = []
    queries: list[tuple[str, str]] = []
    for name in ["json/decoder.py", "shutil.py", "textwrap.py", "csv.py", "tarfile.py", "zipfile/__init__.py", "ipaddress.py", "gzip.py", "difflib.py", "calendar.py", "fractions.py", "statistics.py"]:
        tree = ast.parse((lib / name).read_text(encoding="utf-8"))
        src = (lib / name).read_text(encoding="utf-8")
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            doc = ast.get_docstring(node)
            if not doc or len(doc.split()) < 6 or len(node.body) < 2:
                continue
            body_start = node.body[1].lineno
            lines = src.splitlines()
            code = "\n".join([lines[node.lineno - 1], *lines[body_start - 1 : node.end_lineno]])
            pid = f"C{len(docs)}"
            docs.append((pid, f"{name}\n{code}"[:1500]))
            queries.append((doc.split("\n\n")[0].replace("\n", " ")[:200], pid))
            if len(docs) >= limit:
                return docs, queries
    return docs, queries


def prose_corpus() -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    for path in sorted((ROOT.parent / "docs" / "architecture").glob("*.md")) + sorted((ROOT.parent / "docs" / "adr").glob("0*.md")):
        for section in re.split(r"(?m)^(?=#{1,3} )", path.read_text(encoding="utf-8")):
            text = section.strip()
            if len(text) > 80:
                docs.append((f"{path.stem}#{text.splitlines()[0].lstrip('# ').strip()}", text[:1800]))
    return docs


TOKEN = re.compile(r"\w+", re.UNICODE)


def tokens(text: str) -> list[str]:
    out: list[str] = []
    for t in TOKEN.findall(text):
        out.append(t.lower())
        # getUserById also matches "user", and snake_case likewise.
        parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", t).replace("_", " ").split()
        if len(parts) > 1:
            out.extend(p.lower() for p in parts)
    return out


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.2, b: float = 0.75) -> None:
        self.tf = []
        df: dict[str, int] = {}
        for d in docs:
            counts: dict[str, int] = {}
            for t in tokens(d):
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts:
                df[t] = df.get(t, 0) + 1
        self.lens = np.array([sum(c.values()) for c in self.tf], dtype=float)
        self.avg = self.lens.mean()
        self.idf = {t: float(np.log(1 + (len(docs) - n + 0.5) / (n + 0.5))) for t, n in df.items()}
        self.k1, self.b = k1, b

    def scores(self, q: str) -> np.ndarray:
        s = np.zeros(len(self.tf))
        for t in set(tokens(q)):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, c in enumerate(self.tf):
                f = c.get(t)
                if f:
                    s[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg))
        return s


def rrf(rankings: list[np.ndarray], k: int = 60) -> np.ndarray:
    n = len(rankings[0])
    s = np.zeros(n)
    for r in rankings:
        for rank, idx in enumerate(r):
            s[idx] += 1.0 / (k + rank + 1)
    return np.argsort(-s)


def metrics(ranked_ids: list[list[str]], expected: list[str]) -> dict[str, float]:
    hits = [e in r[:TOP_K] for r, e in zip(ranked_ids, expected)]
    rr = [1.0 / (r.index(e) + 1) if e in r else 0.0 for r, e in zip(ranked_ids, expected)]
    return {"recall@6": round(float(np.mean(hits)), 3), "mrr": round(float(np.mean(rr)), 3), "n": len(expected)}


def main() -> None:
    embed_names = sys.argv[1].split(",")
    rerank_names = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else []

    code_docs, code_q = code_corpus()
    prose = prose_corpus()
    docs = code_docs + prose + TICKETS  # one shared index, as ADR 0005 proposes
    ids = [d[0] for d in docs]
    texts = [d[1] for d in docs]
    pos = {i: n for n, i in enumerate(ids)}
    sets: dict[str, list[tuple[str, str]]] = {
        "code": code_q,
        "prose": [q for q in PROSE_QUERIES],
        "tickets": TICKET_QUERIES,
    }
    for name, qs in sets.items():
        missing = [e for _, e in qs if e not in pos]
        assert not missing, (name, missing[:3])
    print(f"corpus {len(docs)} (code {len(code_docs)}, prose {len(prose)}, tickets {len(TICKETS)})", flush=True)

    bm25 = BM25(texts)
    rerankers = {n: TextCrossEncoder(n, cache_dir=CACHE, threads=4) for n in rerank_names}
    results = []
    for name in embed_names:
        t0 = time.perf_counter()
        model = TextEmbedding(name, cache_dir=CACHE, threads=4)
        load = time.perf_counter() - t0
        t0 = time.perf_counter()
        E = np.array(list(model.passage_embed(texts, batch_size=16)), dtype=np.float32)
        secs = time.perf_counter() - t0
        E /= np.linalg.norm(E, axis=1, keepdims=True)
        row = {"model": name, "load_s": round(load, 1), "docs_per_s": round(len(texts) / secs, 1), "sets": {}}
        for sname, qs in sets.items():
            qtext = [q for q, _ in qs]
            exp = [e for _, e in qs]
            Q = np.array(list(model.query_embed(qtext)), dtype=np.float32)
            Q /= np.linalg.norm(Q, axis=1, keepdims=True)
            naive, hybrid = [], []
            cand_ix = []
            for i, q in enumerate(qtext):
                vr = np.argsort(-(E @ Q[i]))
                kr = np.argsort(-bm25.scores(q))
                h = rrf([vr, kr])
                naive.append([ids[j] for j in vr[:CANDIDATES]])
                hybrid.append([ids[j] for j in h[:CANDIDATES]])
                cand_ix.append(h[:CANDIDATES])
            row["sets"][sname] = {"naive": metrics(naive, exp), "hybrid": metrics(hybrid, exp)}
            for rname, rr in rerankers.items():
                t1 = time.perf_counter()
                ranked = []
                for i, q in enumerate(qtext):
                    scores = list(rr.rerank(q, [texts[j] for j in cand_ix[i]], batch_size=8))
                    order = np.argsort(-np.array(scores))
                    ranked.append([ids[cand_ix[i][j]] for j in order])
                m = metrics(ranked, exp)
                m["ms_per_query"] = round((time.perf_counter() - t1) / len(qtext) * 1000)
                row["sets"][sname][f"hybrid+{rname.split('/')[-1]}"] = m
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    bm_only = {}
    for sname, qs in sets.items():
        ranked = [[ids[j] for j in np.argsort(-bm25.scores(q))[:CANDIDATES]] for q, _ in qs]
        bm_only[sname] = metrics(ranked, [e for _, e in qs])
    print(json.dumps({"bm25_only": bm_only}), flush=True)
    (ROOT / "results" / "retrieval.json").write_text(json.dumps({"results": results, "bm25_only": bm_only}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
