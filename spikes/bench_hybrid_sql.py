"""Find out why filtered hybrid search was slow, and whether the SQL or the store is to blame."""
from __future__ import annotations
import json, shutil, sys, time
from pathlib import Path
import numpy as np
from bench_sqlite_vec import WORK, build, unit, ms, connect

COLL = "SELECT id FROM passage WHERE collection IN (1,2)"
VEC = f"SELECT id, row_number() OVER (ORDER BY distance) AS r FROM passage_vec WHERE embedding MATCH :q AND k = 40 AND id IN ({COLL})"
# Keyword variants
KW_OLD = "SELECT rowid AS id, row_number() OVER (ORDER BY rank) AS r FROM passage_fts WHERE passage_fts MATCH :terms AND rowid IN (" + COLL + ") LIMIT 40"
KW_JOIN = """SELECT f.rowid AS id, row_number() OVER (ORDER BY f.rank) AS r
  FROM passage_fts f JOIN passage p ON p.id = f.rowid
  WHERE passage_fts MATCH :terms AND p.collection IN (1,2) LIMIT 40"""
KW_ORDER = """SELECT id, row_number() OVER () AS r FROM (
  SELECT f.rowid AS id FROM passage_fts f JOIN passage p ON p.id = f.rowid
  WHERE passage_fts MATCH :terms AND p.collection IN (1,2) ORDER BY f.rank LIMIT 40)"""
FUSE = "SELECT id, sum(s) AS score FROM (SELECT id, 1.0/(60+r) AS s FROM v UNION ALL SELECT id, 1.0/(60+r) FROM k) GROUP BY id ORDER BY score DESC LIMIT 40"

def main(n: int) -> None:
    shutil.rmtree(WORK, ignore_errors=True); WORK.mkdir(parents=True)
    dim = 384
    v = unit(n, dim); qs = unit(30, dim)
    con, _ = build(WORK / "h.db", n, dim, v)
    # Add a very common word to about 30% of passages, a worst case for keyword search.
    with con:
        ids = np.random.default_rng(1).choice(n, n * 3 // 10, replace=False)
        con.executemany("UPDATE passage SET text = text || ' common' WHERE id = ?", ((int(i),) for i in ids))
        con.execute("INSERT INTO passage_fts(passage_fts) VALUES('rebuild')")
    rare = lambda i: f"word{i} OR word{i+1}"
    common = lambda i: f"common OR word{i}"
    out = {"passages": n}
    def t(name, sql, terms, count=10, q=True):
        ts = []
        for i in range(count):
            a = {"terms": terms(i)}
            if q: a["q"] = qs[i].tobytes()
            t0 = time.perf_counter(); rows = con.execute(sql, a).fetchall(); ts.append(time.perf_counter() - t0)
        out[name] = {"p50_ms": ms(ts, 50), "rows": len(rows)}
        print(name, out[name], flush=True)
    t("keyword_old_rowid_in_rare", KW_OLD, rare, count=3, q=False)
    t("keyword_join_rare", KW_JOIN, rare, q=False)
    t("keyword_order_limit_rare", KW_ORDER, rare, q=False)
    t("keyword_order_limit_common", KW_ORDER, common, q=False)
    hyb = f"WITH v AS ({VEC}), k AS ({KW_ORDER}) {FUSE}"
    t("hybrid_new_rare", hyb, rare, count=20)
    t("hybrid_new_common", hyb, common, count=20)
    (Path(__file__).parent / "results" / f"hybrid_sql_{n}.json").write_text(json.dumps(out, indent=1))
    con.close(); shutil.rmtree(WORK, ignore_errors=True)

if __name__ == "__main__":
    for n in map(int, sys.argv[1:]): main(n)
