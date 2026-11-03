"""Evaluate sqlite-vec plus FTS5 as the only store, replacing LanceDB.

Covers what ADR 0004 and connectors.md need: speed at several sizes, filters on many
fields, hybrid search in one query, updates and deletes, atomic publish, crash safety,
memory, and exact agreement with brute force.
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import sqlite_vec

WORK = Path(__file__).parent / ".cache" / "sv"
rng = np.random.default_rng(11)
words = np.array([f"word{i}" for i in range(5000)])
FIELDS = 40


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def unit(n: int, dim: int) -> np.ndarray:
    v = rng.standard_normal((n, dim), dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def ms(values: list[float], q: float) -> float:
    return round(float(np.percentile(values, q)) * 1000, 1)


def build(path: Path, n: int, dim: int, vectors: np.ndarray) -> tuple[sqlite3.Connection, float]:
    con = connect(path)
    con.executescript(
        f"""
        CREATE TABLE passage(id INTEGER PRIMARY KEY, record_id INTEGER, collection INTEGER, text TEXT);
        CREATE INDEX passage_collection ON passage(collection);
        CREATE TABLE record_fields(record_id INTEGER, name TEXT, value TEXT);
        CREATE INDEX rf ON record_fields(name, value, record_id);
        CREATE VIRTUAL TABLE passage_vec USING vec0(id INTEGER PRIMARY KEY, embedding FLOAT[{dim}] distance_metric=cosine);
        CREATE VIRTUAL TABLE passage_fts USING fts5(text, content='passage', content_rowid='id', tokenize='unicode61');
        """
    )
    t = time.perf_counter()
    with con:
        for start in range(0, n, 5000):
            end = min(start + 5000, n)
            rows = [(i, i // 5, int(rng.integers(0, 8)), " ".join(rng.choice(words, 60))) for i in range(start, end)]
            con.executemany("INSERT INTO passage VALUES (?,?,?,?)", rows)
            con.executemany("INSERT INTO passage_vec(id, embedding) VALUES (?,?)", ((i, vectors[i].tobytes()) for i in range(start, end)))
            con.executemany("INSERT INTO passage_fts(rowid, text) VALUES (?,?)", ((r[0], r[3]) for r in rows))
    # 40 declared fields on a sample of tickets: one fifth of a passage count.
    field_rows = ((rid, f"f{j}", f"v{int(rng.integers(0, 20))}") for rid in range(n // 5) for j in range(FIELDS))
    with con:
        con.executemany("INSERT INTO record_fields VALUES (?,?,?)", field_rows)
    return con, time.perf_counter() - t


HYBRID = """
WITH v AS (
  SELECT id, row_number() OVER (ORDER BY distance) AS r FROM passage_vec
  WHERE embedding MATCH :q AND k = 40 {vfilter}
), k AS (
  SELECT rowid AS id, row_number() OVER (ORDER BY rank) AS r FROM passage_fts
  WHERE passage_fts MATCH :terms {kfilter} LIMIT 40
)
SELECT id, sum(s) AS score FROM (
  SELECT id, 1.0 / (60 + r) AS s FROM v UNION ALL SELECT id, 1.0 / (60 + r) FROM k
) GROUP BY id ORDER BY score DESC LIMIT 40
"""


def run_size(n: int, dim: int) -> dict[str, object]:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    vectors = unit(n, dim)
    queries = unit(100, dim)
    path = WORK / "s.db"
    con, build_s = build(path, n, dim, vectors)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def timed(fn, count: int = 100) -> list[float]:
        out = []
        for i in range(count):
            t0 = time.perf_counter()
            fn(i)
            out.append(time.perf_counter() - t0)
        return out

    plain = timed(lambda i: con.execute("SELECT id FROM passage_vec WHERE embedding MATCH ? AND k=40", (queries[i].tobytes(),)).fetchall())
    # Filter through ordinary tables, so any number of fields works.
    coll = timed(lambda i: con.execute(
        "SELECT id FROM passage_vec WHERE embedding MATCH ? AND k=40 AND id IN (SELECT id FROM passage WHERE collection IN (1,2))",
        (queries[i].tobytes(),)).fetchall())
    field_filter = (
        "SELECT p.id FROM passage p WHERE p.collection IN (1,2) AND p.record_id IN "
        "(SELECT record_id FROM record_fields WHERE name='f7' AND value='v3')"
    )
    fields = timed(lambda i: con.execute(
        f"SELECT id FROM passage_vec WHERE embedding MATCH ? AND k=40 AND id IN ({field_filter})",
        (queries[i].tobytes(),)).fetchall())
    hybrid = timed(lambda i: con.execute(
        HYBRID.format(vfilter="AND id IN (SELECT id FROM passage WHERE collection IN (1,2))", kfilter="AND rowid IN (SELECT id FROM passage WHERE collection IN (1,2))"),
        {"q": queries[i].tobytes(), "terms": f"word{i} OR word{i + 1}"}).fetchall())

    # Agreement with brute force, filtered and unfiltered.
    agree = []
    for q in queries[:20]:
        got = [r[0] for r in con.execute("SELECT id FROM passage_vec WHERE embedding MATCH ? AND k=10", (q.tobytes(),))]
        agree.append(got == np.argsort(-(vectors @ q))[:10].tolist())
    disk = sum(f.stat().st_size for f in WORK.iterdir())
    res = {
        "passages": n, "dim": dim, "build_s": round(build_s, 1), "disk_mb": round(disk / 1048576),
        "vector_p50_ms": ms(plain, 50), "vector_p95_ms": ms(plain, 95),
        "collection_filter_p50_ms": ms(coll, 50), "collection_filter_p95_ms": ms(coll, 95),
        "field_filter_p50_ms": ms(fields, 50), "field_filter_p95_ms": ms(fields, 95),
        "hybrid_filtered_p50_ms": ms(hybrid, 50), "hybrid_filtered_p95_ms": ms(hybrid, 95),
        "exact_match_brute_force": all(agree),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576),
    }
    con.close()
    return res


def behaviour() -> dict[str, object]:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    dim = 8
    path = WORK / "b.db"
    con = connect(path)
    con.execute(f"CREATE VIRTUAL TABLE v USING vec0(id INTEGER PRIMARY KEY, embedding FLOAT[{dim}])")
    con.execute("CREATE TABLE p(id INTEGER PRIMARY KEY, t TEXT)")
    vec = unit(50, dim)
    with con:
        con.executemany("INSERT INTO v VALUES (?,?)", ((i, vec[i].tobytes()) for i in range(50)))
    out: dict[str, object] = {"sqlite_version": con.execute("select sqlite_version()").fetchone()[0], "vec_version": con.execute("select vec_version()").fetchone()[0]}
    # Atomic publish: vector and record writes roll back together.
    try:
        with con:
            con.execute("INSERT INTO p VALUES (1,'x')")
            con.execute("INSERT INTO v VALUES (100,?)", (vec[0].tobytes(),))
            raise RuntimeError
    except RuntimeError:
        pass
    out["rollback_covers_vectors"] = con.execute("SELECT count(*) FROM v WHERE id=100").fetchone()[0] == 0 and con.execute("SELECT count(*) FROM p").fetchone()[0] == 0
    with con:
        con.execute("DELETE FROM v WHERE id=3")
        con.execute("UPDATE v SET embedding=? WHERE id=4", (vec[10].tobytes(),))
    r = con.execute("SELECT id FROM v WHERE embedding MATCH ? AND k=2 ORDER BY distance", (vec[10].tobytes(),)).fetchall()
    out["delete_update_work"] = {r[0][0], r[1][0]} == {4, 10} and con.execute("SELECT count(*) FROM v WHERE id=3").fetchone()[0] == 0
    # Metadata column limit, and k limit.
    cols = ", ".join(f"m{i} INTEGER" for i in range(17))
    try:
        con.execute(f"CREATE VIRTUAL TABLE v2 USING vec0(embedding FLOAT[4], {cols})")
        out["over_16_metadata_columns"] = "allowed"
    except sqlite3.Error as e:
        out["over_16_metadata_columns"] = str(e)[:90]
    try:
        con.execute("SELECT id FROM v WHERE embedding MATCH ? AND k=5000", (vec[0].tobytes(),)).fetchall()
        out["k_5000"] = "allowed"
    except sqlite3.Error as e:
        out["k_5000"] = str(e)[:90]
    big = list(range(50))
    try:
        got = con.execute("SELECT id FROM v WHERE embedding MATCH ? AND k=3 AND id IN (SELECT value FROM json_each(?))", (vec[0].tobytes(), json.dumps(big))).fetchall()
        out["id_in_subquery"] = len(got) == 3
    except sqlite3.Error as e:
        out["id_in_subquery"] = str(e)[:90]
    con.commit()
    con.close()
    # Crash safety: kill a writer in the middle of a transaction.
    script = (
        "import sqlite3,sqlite_vec,os,struct\n"
        f"c=sqlite3.connect({str(path)!r});c.enable_load_extension(True);sqlite_vec.load(c);c.execute('PRAGMA journal_mode=WAL')\n"
        "c.execute('BEGIN')\n"
        f"[c.execute('INSERT INTO v VALUES (?,?)',(1000+i,struct.pack('8f',*[1.0]*8))) for i in range(2000)]\n"
        "os._exit(9)\n"
    )
    subprocess.run([sys.executable, "-c", script], check=False)
    con = connect(path)
    out["after_crash_integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0]
    out["after_crash_uncommitted_rows"] = con.execute("SELECT count(*) FROM v WHERE id>=1000").fetchone()[0]
    con.close()
    # One writer with many readers.
    a, b = connect(path), connect(path)
    a.execute("BEGIN IMMEDIATE")
    a.execute("INSERT INTO v VALUES (2000,?)", (vec[0].tobytes(),))
    t0 = time.perf_counter()
    b.execute("SELECT id FROM v WHERE embedding MATCH ? AND k=3", (vec[0].tobytes(),)).fetchall()
    out["reader_during_write_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    a.rollback()
    a.close(); b.close()
    pkg = Path(sqlite_vec.__file__).parent
    out["package_kb"] = round(sum(f.stat().st_size for f in pkg.rglob("*") if f.is_file()) / 1024)
    return out


if __name__ == "__main__":
    results: dict[str, object] = {"behaviour": behaviour()}
    print(json.dumps(results["behaviour"], indent=1), flush=True)
    sizes = []
    for n, dim in [(10_000, 384), (100_000, 384), (100_000, 768), (300_000, 384), (1_000_000, 384)]:
        r = run_size(n, dim)
        sizes.append(r)
        print(json.dumps(r), flush=True)
    results["sizes"] = sizes
    (Path(__file__).parent / "results" / "sqlite_vec.json").write_text(json.dumps(results, indent=1))
    shutil.rmtree(WORK, ignore_errors=True)
