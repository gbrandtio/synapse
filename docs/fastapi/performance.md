# FastAPI Performance

Everyday rules for a responsive local API. Python-wide guidance is in [Python Performance](../python/performance.md).

---

## Never block the event loop

This is the most important rule. All requests share one event loop, so one blocking call freezes the whole API, including the progress the user is watching.

| Route type | When it runs | Use for |
|------------|--------------|---------|
| `async def` | On the event loop | Code that uses `await` for all I/O |
| `def` | In a thread pool | Blocking libraries, such as `sqlite3` calls |

**Do**
- Use `asyncio.to_thread` for short blocking calls inside `async` code.
- Send CPU-heavy work, such as parsing, to the process pool.
- Run embedding and re-ranking off the event loop.

```python
# ❌ Stops every other request during the search
@router.post("/search")
async def search(request: SearchRequest) -> SearchResponse:
    return to_response(index.search_blocking(request.query))

# ✅
@router.post("/search")
async def search(request: SearchRequest) -> SearchResponse:
    results = await asyncio.to_thread(index.search_blocking, request.query)
    return to_response(results)
```

**Don't**
- Write `async def` around blocking code. It is worse than plain `def`, which would at least use the thread pool.

---

## Serialization

**Do**
- Declare a return type or `response_model`, so FastAPI uses Pydantic's fast serialization.
- Return only fields the UI needs, and keep summary and detail responses separate.
- Avoid sending passage text in list views.

**Don't**
- Run `model_dump()` and then re-validate, doing the same work twice.
- Return full records when a list screen needs only titles.

---

## Pagination

**Do**
- Paginate every list that can grow. Records and run history can get very large.
- Prefer cursor pagination, using a sorted indexed column, for large tables.
- Set a default limit and a maximum.

```sql
-- ❌ Gets slower with every page
SELECT * FROM records ORDER BY updated_at LIMIT 50 OFFSET 90000

-- ✅ Uses the index directly
SELECT * FROM records WHERE (updated_at, id) < (?, ?) ORDER BY updated_at DESC, id DESC LIMIT 50
```

---

## Streaming

**Do**
- Stream answer text as soon as it arrives.
- Combine very rapid progress updates, sending at most a few per second. The UI cannot show more.
- Stream large downloads and exports with `StreamingResponse`.

**Don't**
- Build a whole answer or export before sending it.
- Read an uploaded file into memory. Desktop clients should pass a selected path, and team mode should stream uploads to disk.

---

## Middleware

**Do**
- Keep middleware few and fast, because it runs on every request.
- Measure request durations and log slow routes.

**Don't**
- Read the request or response body in middleware. It can break streaming, and adds cost.

---

## Review checklist

- [ ] `async def` routes contain no blocking calls.
- [ ] CPU-heavy work is off the event loop.
- [ ] Lists are paginated, with limits.
- [ ] Responses include only what the screen needs.
- [ ] Answers stream immediately, and progress events are throttled.
- [ ] Middleware doesn't touch bodies.
