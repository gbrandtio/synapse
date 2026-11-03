# Python Best Practices

How we structure, run and protect the engine. Style is covered in [Coding Standards](./coding-standards.md).

---

## Project setup and dependencies

**Do**
- Manage everything with `uv`: `uv add`, `uv sync --locked`, and `uv run`.
- Commit `uv.lock`, so that every build gets identical versions.
- Pin the Python version in `.python-version`.
- Split optional heavy features into dependency groups, so that optional packs stay out of the base install.

**Don't**
- Use `pip install` by hand, or rely on the system's Python.
- Add a dependency without checking its licence. CI fails on AGPL or GPL-only licences, because Synapse ships as MIT and bundles its dependencies.

**Why:** The engine ships inside an installer, so a dependency that changes unexpectedly or has an incompatible licence directly reaches users.

---

## Project layout

```
engine/src/synapse_engine/
├─ domain/        Records, passages, blueprints. No framework imports
├─ application/   Use cases: ingest, ask, query records, run workflow
├─ adapters/      connectors/ parsers/ ai/ stores/ secrets/
└─ api/           FastAPI routes and request and response models
```

- `import-linter` enforces these directions in CI.
- Organise by feature inside each layer, and keep code that changes together close together.
- Avoid a catch-all `utils.py`. A helper belongs with the code that uses it.

---

## Errors

**Do**
- Define a small exception hierarchy under one base class, `SynapseError`.
- Catch the most specific exception you can handle, and add context with `raise ... from error`.
- Return a value for expected outcomes, such as "nothing found". Raise for failures.
- Give each error a stable code and a plain message, so the UI can offer a fix.

```python
# ❌ Hides real bugs, and the user learns nothing
try:
    issue = await client.get_issue(key)
except Exception:
    return None

# ✅
try:
    issue = await client.get_issue(key)
except httpx.TimeoutException as error:
    raise SourceUnreachableError(source="jira", target=key) from error
```

**Don't**
- Use bare `except:` or swallow errors silently.
- Catch `asyncio.CancelledError` without re-raising it.
- Put tokens, cookies or full source text in exception messages.

**Why:** Non-technical users rely on error messages to know what to do next, and a swallowed error looks like a wrong answer.

---

## Async

**Do**
- Use `async` for network and database calls, and pass one shared `httpx.AsyncClient` around.
- Use `asyncio.TaskGroup` for related concurrent work, so that one failure cancels the rest.
- Limit concurrency with `asyncio.Semaphore`, particularly when calling Jira or GitHub.
- Set a timeout on every external call with `asyncio.timeout` or the client's own setting.
- Run blocking work with `asyncio.to_thread`, or in the process pool for CPU-heavy work.

```python
# ❌ Blocks every other request while the file is parsed
@router.post("/parse")
async def parse(path: Path) -> Document:
    return parse_pdf(path)

# ✅
async def parse(path: Path) -> Document:
    return await parser_pool.run(parse_pdf, path, timeout_seconds=120)
```

**Don't**
- Start a task with `asyncio.create_task` without keeping a reference to it, because it can be garbage collected mid-run.
- Call `time.sleep`, `requests`, or other blocking code in an `async` function. Ruff's `ASYNC` rules flag many of these.

---

## Configuration and secrets

- Keep user settings in validated blueprints. See [Configuration](../architecture/configuration.md).
- Keep process settings in a `pydantic-settings` class, created at startup and passed to whatever needs it.
- Read secrets through the `SecretStore` adapter, and hold them in `pydantic.SecretStr`, so they don't print in logs.

**Don't**
- Read `os.environ` throughout the code.
- Store secrets in blueprints, logs, checkpoints, or exception messages.

---

## Logging

**Do**
- Use `logging.getLogger(__name__)`, and pass values as fields or arguments.
- Include IDs that help tracing: `job_id`, `collection_id`, and `run_id`.
- Write logs to the app's data folder with rotation, so that users can attach them to a bug report.

**Don't**
- Use `print` in engine code. Its stdout carries the startup handshake.
- Log document text, prompts, tokens or cookies. Users' content is private.

---

## Security

The engine reads untrusted files, repositories and web pages.

**Do**
- Treat all fetched content as hostile data. Validate sizes, and enforce time limits.
- Run parsers in a separate worker process with a time limit.
- Check extracted paths stay inside the expected folder, and check archive sizes before reading.
- Run subprocesses with a list of arguments and `shell=False`.
- Bind only to `127.0.0.1`, and require the per-launch token.
- Block private network addresses in the web connector, unless the user approved that host. Resolve the hostname, connect to the checked address, and repeat the check on every redirect.
- Never follow a symlink that leads outside a repository or selected folder.

```python
# ❌ Allows path traversal
target = base / member.name

# ✅
target = (base / member.name).resolve()
if not target.is_relative_to(base.resolve()):
    raise UnsafeArchiveError(member.name)
```

**Don't**
- Use `pickle`, `eval`, `exec` or `yaml.load` on anything that could come from outside. Use `yaml.safe_load`.
- Run a formula or macro from a spreadsheet, or any hook or config from a git repository.
- Use Jinja or `str.format` to fill prompts. See [ADR 0012](../adr/0012-safe-prompt-filling.md).

---

## Testing

**Do**
- Use `pytest`, with `pytest-asyncio` or `anyio` for async tests.
- Test domain and application code with fakes for its ports. These tests need no network or database.
- Run connector contract tests against recorded responses, for each access method.
- Test failures as well as successes: timeouts, rate limits, malformed files, and partial data.
- Use a fake chat model, so tests are fast and repeatable and never call a real AI.

```python
@pytest.mark.parametrize("cell", ["=1+1", "{{question}}", "<script>alert(1)</script>"])
def test_spreadsheet_cell_is_kept_as_plain_text(cell: str) -> None:
    record = import_row({"Issue key": "SUP-1", "Summary": cell}, mapping=JIRA_MAPPING)
    assert record.title == cell
```

**Don't**
- Depend on test order, wall-clock time, or real network access.
- Mock the thing being tested. Fake only what crosses a boundary.

---

## Review checklist

- [ ] `uv.lock` is updated, and any new dependency has a compatible licence.
- [ ] Layering holds, and there is no catch-all helper module.
- [ ] Errors are specific and carry context, and they contain no secrets or user content.
- [ ] No blocking code runs on the event loop, and external calls have timeouts and concurrency limits.
- [ ] Untrusted input has size limits and time limits, and is never evaluated.
- [ ] Tests cover failure paths, and run with no network or real AI.
