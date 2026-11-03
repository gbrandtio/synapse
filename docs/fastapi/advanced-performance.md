# Advanced FastAPI Performance

For when [Performance](./performance.md) is not enough. Use these only after measuring.

---

## Uvicorn on desktop

**Do**
- Run one worker. A single user does not need more, and each extra process would load its own models and open its own databases.
- Run Uvicorn from code on an already bound socket, using port 0. Checking for a free port and binding later leaves a gap where another process could take it, and the client would then send it the token.
- Set `timeout_graceful_shutdown`, so that a stuck stream cannot stop the engine from exiting.
- Use `uvloop` and `httptools` only where they provide wheels on each platform. Measure before bundling them, because they add packaging work and do little for one local client.

```python
socket_ = socket.create_server(("127.0.0.1", 0))  # The OS picks a free port
port = socket_.getsockname()[1]
config = uvicorn.Config(app, log_config=None, timeout_graceful_shutdown=5)
report_ready(port)
await uvicorn.Server(config).serve(sockets=[socket_])
```

**Don't**
- Use `--reload` outside development.
- Copy server tuning advice written for high-traffic sites. Here, memory and responsiveness matter most, not requests per second.

---

## Keeping the API responsive under load

During big syncs, background work competes with the API.

**Do**
- Run the job runner with its own limits, separate from requests.
- Reserve capacity for user actions. For example, use a separate thread pool for search and for background embedding.
- Set a size for the default thread pool deliberately, since `def` routes and `to_thread` share it.
- Give the user's question priority over indexing.

**Why:** The user judges the app by whether it responds immediately, not by how fast background indexing finishes.

---

## Backpressure in streams

A slow client should never make the engine use unbounded memory.

**Do**
- Use a bounded `asyncio.Queue` between a job and its viewers.
- For progress, drop older events and keep the latest, because only the latest matters.
- For answers, never drop tokens. Slow the producer instead, which an `async for` generator does naturally.

```python
async def publish_progress(queue: asyncio.Queue[Progress], update: Progress) -> None:
    if queue.full():
        queue.get_nowait()  # Only the newest progress is worth showing
    queue.put_nowait(update)
```

**Don't**
- Use an unbounded queue per subscriber.

---

## Monitoring the event loop

**Do**
- Run a small background task in development that measures how late `asyncio.sleep` wakes up. Late wake-ups indicate blocking code.
- Turn on `PYTHONASYNCIODEBUG=1` in test runs, which logs slow callbacks.
- Use `py-spy dump --pid <pid>` to see what a stuck engine is doing.

```python
async def watch_event_loop(interval: float = 0.1, limit: float = 0.25) -> None:
    while True:
        started = time.perf_counter()
        await asyncio.sleep(interval)
        lag = time.perf_counter() - started - interval
        if lag > limit:
            logger.warning("event loop lag: %.3fs", lag)
```

---

## Startup

**Do**
- Create the app quickly, then report "ready" on stdout once the socket is listening.
- Move slow setup, such as opening the search index, to first use or a background task.
- Track engine start time in CI.

**Don't**
- Import heavy libraries at module level in route files. See [Startup time](../python/advanced-performance.md#startup-time).

---

## Review checklist

- [ ] One Uvicorn worker on desktop, with graceful shutdown limits.
- [ ] Background work has its own limits, and user actions come first.
- [ ] Stream queues are bounded, and answer tokens are never dropped.
- [ ] Event-loop lag is checked in test runs.
- [ ] Startup time is measured, with heavy imports deferred.
