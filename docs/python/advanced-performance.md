# Advanced Python Performance

For when [Performance](./performance.md) is not enough. Use these only after a profile shows the need.

---

## Profiling

| Question | Tool |
|----------|------|
| Where does CPU time go in a running engine? | `py-spy top --pid <pid>` and `py-spy record -o profile.svg --pid <pid>` |
| Which function is slowest in a script? | `python -m cProfile -o out.prof script.py`, viewed with `snakeviz` |
| Which lines allocate memory? | `tracemalloc`, or `memray run script.py` |
| Is the event loop blocked? | `PYTHONASYNCIODEBUG=1`, which logs slow callbacks |
| What slows startup? | `python -X importtime -m synapse_engine 2> imports.log` |

**Do**
- Profile a built package as well as a dev environment. The two can behave differently.
- Keep benchmark scripts in `engine/benchmarks/`, with fixed sample data.

---

## The GIL: threads or processes

The standard Python 3.13 build has a Global Interpreter Lock: only one thread runs Python code at a time. C libraries may release it while they work.

| Work | Use | Reason |
|------|-----|--------|
| Network and database calls | `asyncio` | Mostly waiting, so a single thread handles many |
| Blocking I/O without an async API | `asyncio.to_thread` | The lock is released while waiting |
| ONNX embedding and re-ranking | Thread | Native code typically releases the lock, which should be confirmed by measurement |
| Parsing documents, splitting large text | Process pool | Python-level CPU work holds the lock, and a parser crash must not kill the engine |

**Don't**
- Adopt the free-threaded Python build. Native libraries must support it first, and that has not been tested for Synapse.

---

## Process pools

**Do**
- Keep a small pool for parsers, and replace a worker after a set number of tasks, so memory leaks in native parsers stay contained.
- Use the `spawn` start method on all platforms, for consistent behaviour.
- Pass file paths to workers, not file contents.
- Enforce a hard time limit by killing the worker, because a stuck native call cannot be cancelled from Python.
- Treat a dead worker as "this file failed", and continue with the rest.

```python
# ❌ Copies the whole file between processes
await pool.run(parse_pdf, path.read_bytes())

# ✅ The worker reads the file itself
await pool.run(parse_pdf, path, timeout_seconds=120)
```

---

## Native libraries and thread counts

ONNX Runtime and the local llama.cpp server can each use many CPU threads. Together, they can oversubscribe the CPU and make everything slower.

**Do**
- Set thread limits explicitly, based on the computer's core count.
- Avoid running embedding and local AI generation at full speed together. Give priority to the user's question, and pause or slow background ingestion while answering.
- Measure with real sizes, because the best embedding batch size depends on text length as well as count.

**Why:** A user asking a question cares more about the answer than about background indexing.

---

## SQLite tuning

The engine's single SQLite file serves records, jobs and checkpoints.

```python
connection.execute("PRAGMA journal_mode=WAL")      # Readers don't block the writer
connection.execute("PRAGMA synchronous=NORMAL")    # Fast, and safe with WAL
connection.execute("PRAGMA foreign_keys=ON")
connection.execute("PRAGMA busy_timeout=5000")     # Wait instead of failing immediately
```

**Do**
- Use one writer, and queue writes through it.
- Index the columns you filter on, and check query plans with `EXPLAIN QUERY PLAN`.
- Keep write transactions short.

**Don't**
- Place the database on a network folder, where SQLite locking and WAL are unreliable. This matters for the Data location setting.

---

## sqlite-vec and FTS5

**Do**
- Filter vectors with `id IN (subquery)` on ordinary indexed tables, so scoping happens before ranking.
- Filter FTS5 results with a join, then `ORDER BY rank LIMIT n`.
- Write in batches inside one transaction, with WAL mode on.
- Keep a speed test on the real hybrid query.

**Don't**
- Use `rowid IN (subquery)` on an FTS5 table. It took 1.6 s at 100,000 passages and 11 s at 300,000, against 1 to 12 ms for a join at 100,000.
- Add `vec0` metadata columns for fields. They stop at 16, and adding one means rebuilding the table.

---

## Streaming large files

**Do**
- Read Excel with `openpyxl.load_workbook(path, read_only=True, data_only=True)`, which streams rows and returns stored values. Call `workbook.close()` afterwards, and install `defusedxml`, which `openpyxl` uses to guard against XML entity-expansion attacks.
- Read repository archives with `tarfile.open(mode="r|gz")`, the forward-only streaming mode.
- Check archive member sizes as you read, and stop at a limit.

---

## Startup time

The app should feel ready quickly, and imports are often the slowest part.

**Do**
- Import heavy libraries inside the adapter function that needs them.
- Report "ready" before loading models, then load them when first used or in the background.
- Check `-X importtime` in CI against a limit.

```python
# ❌ Every launch pays for this, even with no search
from fastembed import TextEmbedding

# ✅
if TYPE_CHECKING:
    from fastembed import TextEmbedding

def load_embedder(path: Path) -> "TextEmbedding":
    from fastembed import TextEmbedding  # Slow to import, and only needed once search starts
    return TextEmbedding(MODEL_NAME, cache_dir=str(path), local_files_only=True)
```

---

## Review checklist

- [ ] An advanced technique is justified by a profile, and its numbers are in the PR.
- [ ] CPU-heavy Python work runs in a process pool, with hard time limits.
- [ ] Thread limits are set, and background work gives way to the user's question.
- [ ] SQLite uses WAL, with one writer and indexed filters.
- [ ] Vector filters use `id IN (subquery)`, FTS5 filters use a join, and filter columns are indexed.
- [ ] Heavy imports stay out of startup, and startup time is checked in CI.
