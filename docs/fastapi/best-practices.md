# FastAPI Best Practices

How to run the engine's API reliably and safely.

---

## Lifespan

**Do**
- Open and close shared resources in a `lifespan` function: database connections, HTTP clients, job runner, and worker pool.
- Store them on `app.state`, or in a typed container that dependencies read.
- Close them in reverse order after `yield`.

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = await Container.open(settings)
    app.state.container = container
    try:
        yield
    finally:
        await container.close()

app = FastAPI(lifespan=lifespan)
```

**Don't**
- Use `@app.on_event`. It is deprecated, and these handlers do not run when a `lifespan` is set.
- Load heavy models during startup. The engine should report "ready" quickly, and load them when needed.

---

## Dependencies

**Do**
- Provide use cases and services through `Depends`, using `Annotated` aliases.
- Override dependencies in tests through `app.dependency_overrides`.
- Keep the object graph in one composition root.

```python
ContainerDep = Annotated[Container, Depends(get_container)]

def get_start_sync(container: ContainerDep) -> StartSync:
    return container.start_sync
```

**Don't**
- Import global instances into routes.
- Put business decisions in a dependency. Dependencies should only provide things, or reject requests.

---

## Local security

The API runs on the user's computer, and other local software or websites could try to reach it.

**Do**
- Bind only to `127.0.0.1`, and refuse anything else in desktop mode.
- Require the per-launch token on every route, using a global dependency.
- Compare tokens with `secrets.compare_digest`.
- Check the `Host` header using `TrustedHostMiddleware`, which defends against DNS rebinding from a website.
- Allow no browser origins by default. The desktop client does not use CORS, and team mode must decide this explicitly.
- Validate paths from clients, and keep any file access to what the user selected.

```python
async def require_token(
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = f"Bearer {settings.session_token.get_secret_value()}".encode()
    # Compare bytes: compare_digest raises TypeError on non-ASCII strings.
    if not secrets.compare_digest((authorization or "").encode(), expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

app = FastAPI(lifespan=lifespan, dependencies=[Depends(require_token)])
```

**Don't**
- Assume localhost makes it safe.
- Log the token, or put it in URLs.
- Keep `/docs` and `/openapi.json` reachable in release builds.

---

## Errors

**Do**
- Register one exception handler that maps `SynapseError` to a consistent response.
- Return a stable error `code`, a plain `message`, and an optional `action` that the UI can turn into a button.
- Log unexpected exceptions with a reference ID, and return only the ID and a generic message.

```python
class ErrorResponse(BaseModel):
    code: str
    message: str
    action: str | None = None

@app.exception_handler(SynapseError)
async def handle_synapse_error(_: Request, error: SynapseError) -> JSONResponse:
    body = ErrorResponse(code=error.code, message=error.user_message, action=error.action)
    return JSONResponse(status_code=error.http_status, content=body.model_dump())
```

**Don't**
- Send stack traces, file contents, or tokens to the client.
- Return `200` with an error inside the body.

---

## Long-running work

**Do**
- Return `202 Accepted` with a job ID for sync, import and workflow runs.
- Store jobs in SQLite, so they resume after a restart.
- Let the client follow progress by SSE, and fetch current state through a normal route when it reconnects.

**Don't**
- Use `BackgroundTasks` for this. It runs after the response and is lost when the process stops, so it has no persistence or cancellation.
- Hold a request open until a long job completes.

---

## Server-Sent Events

**Do**
- Use FastAPI's built-in support from `fastapi.sse`, available since 0.135.
- Give events a clear type and an `id`, so that clients can reconnect.
- Stop work when the client disconnects, if the work belongs to that connection, such as an answer.

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@router.post("/assistants/{assistant_id}/ask", response_class=EventSourceResponse)
async def ask(request: AskRequest, use_case: AskDep) -> AsyncIterable[ServerSentEvent]:
    async for event in use_case.stream(request.question):
        yield ServerSentEvent(data=event.to_response(), event=event.kind)
```

**Don't**
- Add `sse-starlette`, which is no longer needed.
- Cancel a background job when its progress stream closes. Jobs should outlive their viewers.

---

## Testing

**Do**
- Use `httpx.AsyncClient` with `ASGITransport` to test routes in process.
- Override dependencies with fakes, and focus on the HTTP contract: status codes, shapes, and auth.
- Test that requests without a token are rejected, for all routes.
- Test SSE by reading through to the final event, including errors partway through a stream.

**Don't**
- Start a real server, unless the test is checking the startup handshake.

---

## Review checklist

- [ ] Resources are managed in `lifespan`, and `on_event` is not used.
- [ ] All routes require the token, the host is checked, and the API binds to localhost.
- [ ] Errors use the shared format, and expose no internals.
- [ ] Long-running work uses persistent jobs, not `BackgroundTasks`.
- [ ] SSE uses `fastapi.sse`, and disconnects are handled.
- [ ] Tests cover status codes, auth and failures.
