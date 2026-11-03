# Python Performance

Everyday rules for keeping the engine fast on an ordinary laptop. Deeper techniques are in [Advanced Performance](./advanced-performance.md).

---

## How to approach performance

**Do**
- **Measure before you change anything.** Find the slow part, then fix that part only.
- Use realistic input: a 500-page PDF, a large repository, and 100,000 passages.
- Record the before and after numbers in the PR.
- Know the targets we care about most: time to first answer word, documents processed per minute, and peak memory.

**Don't**
- Optimise code because it *looks* slow. In this engine, most time goes to parsing, embedding, and AI calls.
- Trust a single run.

```python
# Quick comparisons
# uv run python -m timeit -s "from m import data, f" "f(data)"
```

**Why:** Python-level tweaks rarely matter when a model call takes seconds. Measuring prevents effort on the wrong thing.

---

## Do less work

The cheapest work is work you skip. This is the biggest performance tool in a RAG system.

**Do**
- Hash content first, and skip anything unchanged.
- Cache embeddings by content hash and model, so re-syncing costs almost nothing.
- Request only needed fields from Jira and GitHub.
- Use conditional requests and `since` filters for incremental sync.

```python
# ❌ Re-embeds everything on every sync
vectors = embedder.embed([passage.text for passage in passages])

# ✅
missing = [p for p in passages if p.content_hash not in cache]
cache.store(missing, embedder.embed([p.text for p in missing]))
```

---

## Batching

**Do**
- Embed and insert in batches. One call with 64 texts is far faster than 64 calls with one text.
- Commit SQLite writes in transactions, rather than one row at a time.
- Keep batch sizes configurable, because the best size depends on memory.

```python
# ❌ One transaction per row, with a disk sync for each
for record in records:
    connection.execute(INSERT_RECORD, record.as_row())
    connection.commit()

# ✅
with connection:
    connection.executemany(INSERT_RECORD, (r.as_row() for r in records))
```

---

## Network and concurrency

**Do**
- Reuse one `httpx.AsyncClient`, so that connections are reused.
- Fetch concurrently with a small limit, and respect `Retry-After`.
- Page through results as a stream, and store progress as you go.

**Don't**
- Create a new client per request.
- Start unlimited tasks with `asyncio.gather` over thousands of items.

```python
# ❌ Thousands of tasks start at once
await asyncio.gather(*(fetch(ref) for ref in refs))

# ✅
limit = asyncio.Semaphore(4)

async def fetch_limited(ref: ItemRef) -> Record:
    async with limit:
        return await fetch(ref)

async with asyncio.TaskGroup() as group:
    tasks = [group.create_task(fetch_limited(ref)) for ref in page]
```

---

## Memory

Users run Synapse beside a local AI model, on computers with as little as 8 GB of memory.

**Do**
- Process documents and records as streams, using generators.
- Read large files in chunks, and stream archives without unpacking them to memory.
- Load models once, and share them. Release optional models when idle.
- Use `slots=True` on dataclasses created in large numbers.

**Don't**
- Hold a whole collection in a list, or call `file.read()` on a file of unknown size.
- Convert search results to pandas only for convenience. Arrow or plain objects cost less.

---

## Everyday Python

These matter only on real hot paths, such as splitting text.

| Prefer | Over | Why |
|--------|------|-----|
| `"".join(parts)` | `text += part` in a loop | Repeated `+=` can copy the text each time |
| `set` or `dict` lookup | `x in some_list` | Constant time rather than a scan |
| `collections.deque` | `list.pop(0)` | `pop(0)` shifts every element |
| Generators | Building a list you only loop over once | Lower peak memory |
| `re.compile` at module level | Compiling a pattern inside a loop | Avoids repeated cache lookups |

**Don't**
- Write unsafe regular expressions on untrusted text. Nested quantifiers can take exponential time.

---

## Review checklist

- [ ] Performance changes include before and after numbers, using realistic input.
- [ ] Unchanged content is skipped through hashes or caches.
- [ ] Embedding and database writes run in batches.
- [ ] Concurrency has a limit, and HTTP clients are reused.
- [ ] Large inputs are streamed, and never fully loaded into memory.
- [ ] Regular expressions on untrusted text cannot run away.
