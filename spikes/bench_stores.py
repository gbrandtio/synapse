"""Phase 0 test 4: LanceDB at about 100,000 passages with many filter columns, against sqlite-vec.

Vectors are random and normalised, which is a worst case for approximate indexes and says
nothing about answer quality. This measures speed, disk and memory only.
"""
from __future__ import annotations

import json
import resource
import shutil
import sqlite3
import struct
import time
from pathlib import Path

import lancedb
import numpy as np
import pyarrow as pa
import sqlite_vec

N = 100_000
DIM = 384
FILTER_COLUMNS = 30
QUERIES = 200
WORK = Path(__file__).parent / ".cache" / "stores"
rng = np.random.default_rng(7)


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576  # bytes on macOS


def size_mb(p: Path) -> float:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1048576


def pct(values: list[float], q: float) -> float:
    return round(float(np.percentile(values, q)) * 1000, 1)


def main() -> None:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    vectors = rng.standard_normal((N, DIM), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    words = np.array([f"word{i}" for i in range(5000)])
    texts = [" ".join(rng.choice(words, 60)) for _ in range(N)]
    collections = rng.integers(0, 8, N)
    status = rng.integers(0, 6, N)
    extra = {f"f{i}": rng.integers(0, 50, N) for i in range(FILTER_COLUMNS)}
    queries = rng.standard_normal((QUERIES, DIM), dtype=np.float32)
    queries /= np.linalg.norm(queries, axis=1, keepdims=True)
    out: dict[str, dict[str, float]] = {}

    # LanceDB
    db = lancedb.connect(WORK / "lance")
    table = pa.table(
        {
            "id": pa.array(range(N)),
            "vector": pa.FixedSizeListArray.from_arrays(pa.array(vectors.ravel()), DIM),
            "text": pa.array(texts),
            "collection": pa.array(collections),
            "status": pa.array(status),
            **{k: pa.array(v) for k, v in extra.items()},
        }
    )
    t = time.perf_counter()
    tbl = db.create_table("passages", table)
    write_s = time.perf_counter() - t
    t = time.perf_counter()
    tbl.create_index(metric="cosine", vector_column_name="vector", index_type="IVF_PQ", num_partitions=256, num_sub_vectors=48)
    tbl.create_scalar_index("collection", index_type="BITMAP")
    tbl.create_scalar_index("status", index_type="BITMAP")
    tbl.create_fts_index("text")
    index_s = time.perf_counter() - t

    def run(fn) -> list[float]:
        times = []
        for q in queries:
            t0 = time.perf_counter()
            fn(q)
            times.append(time.perf_counter() - t0)
        return times

    plain = run(lambda q: tbl.search(q).metric("cosine").limit(40).to_arrow())
    filt = run(lambda q: tbl.search(q).metric("cosine").where("collection IN (1,2) AND status = 3 AND f7 < 25", prefilter=True).limit(40).to_arrow())
    hybrid_times = []
    for i in range(QUERIES // 4):
        t0 = time.perf_counter()
        tbl.search(f"word{i} word{i + 1}", query_type="fts").where("collection IN (1,2)", prefilter=True).limit(40).to_arrow()
        hybrid_times.append(time.perf_counter() - t0)
    # Recall of the approximate index, against exact search.
    agree = []
    for q in queries[:50]:
        approx = set(tbl.search(q).metric("cosine").limit(10).nprobes(20).refine_factor(5).to_arrow()["id"].to_pylist())
        exact = set(np.argsort(-(vectors @ q))[:10].tolist())
        agree.append(len(approx & exact) / 10)
    out["lancedb"] = {
        "write_s": round(write_s, 1),
        "index_s": round(index_s, 1),
        "disk_mb": round(size_mb(WORK / "lance")),
        "vector_p50_ms": pct(plain, 50),
        "vector_p95_ms": pct(plain, 95),
        "filtered_p50_ms": pct(filt, 50),
        "filtered_p95_ms": pct(filt, 95),
        "keyword_filtered_p50_ms": pct(hybrid_times, 50),
        "recall_at_10_random_vectors": round(float(np.mean(agree)), 3),
        "peak_rss_mb_so_far": round(rss_mb()),
    }
    print(json.dumps(out["lancedb"]), flush=True)

    # sqlite-vec: exact scan, with filter via partition or auxiliary columns.
    con = sqlite3.connect(WORK / "vec.db")
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    con.execute(f"CREATE VIRTUAL TABLE passages USING vec0(id INTEGER PRIMARY KEY, embedding FLOAT[{DIM}] distance_metric=cosine, collection INTEGER, status INTEGER)")
    t = time.perf_counter()
    con.executemany(
        "INSERT INTO passages(id, embedding, collection, status) VALUES (?,?,?,?)",
        ((int(i), vectors[i].tobytes(), int(collections[i]), int(status[i])) for i in range(N)),
    )
    con.commit()
    vec_write = time.perf_counter() - t
    plain = run(lambda q: con.execute("SELECT id FROM passages WHERE embedding MATCH ? AND k = 40", (q.tobytes(),)).fetchall())
    filt = run(lambda q: con.execute("SELECT id FROM passages WHERE embedding MATCH ? AND k = 40 AND collection IN (1,2) AND status = 3", (q.tobytes(),)).fetchall())
    out["sqlite_vec"] = {
        "write_s": round(vec_write, 1),
        "disk_mb": round((WORK / "vec.db").stat().st_size / 1048576),
        "vector_p50_ms": pct(plain, 50),
        "vector_p95_ms": pct(plain, 95),
        "filtered_p50_ms": pct(filt, 50),
        "filtered_p95_ms": pct(filt, 95),
        "recall_at_10_random_vectors": 1.0,
    }
    print(json.dumps(out["sqlite_vec"]), flush=True)
    (Path(__file__).parent / "results" / "stores.json").write_text(json.dumps(out, indent=1))
    shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    main()
