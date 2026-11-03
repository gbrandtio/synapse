# Python Coding Standards

How Synapse's Python code should look. Tools enforce most of this, so reviews can focus on behaviour.

---

## Formatting and linting

**Do**
- Run `uv run ruff format` and `uv run ruff check --fix` before every commit. CI fails if they would change anything.
- Run `uv run mypy src tests`. CI uses strict mode.
- Keep configuration in `engine/pyproject.toml`, so there is one place to look.

```toml
[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "C4", "DTZ", "S", "SIM", "RET", "PTH", "ASYNC", "RUF"]

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
```

**Don't**
- Silence a rule with `# noqa` or `# type: ignore` without naming the rule and giving a reason.

**Why:** Style arguments waste review time, and tools settle them instantly.

---

## Naming

| Kind | Style | Example |
|------|-------|---------|
| Modules and packages | `lower_snake_case` | `jira_connector.py` |
| Functions, variables | `lower_snake_case` | `fetch_issue`, `retry_count` |
| Classes, type aliases | `UpperCamelCase` | `SearchResult`, `RecordId` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_PASSAGE_TOKENS` |
| Private names | Leading underscore | `_parse_comment` |
| Booleans | Reads as a question | `is_partial`, `has_comments` |

- Use full words. `passage_count` is better than `pc`.
- Functions are verbs, and classes are nouns.

---

## Type hints

**Do**
- Type every function parameter and return value, including tests.
- Use modern syntax: `list[str]`, `str | None`, and `type RecordId = str`.
- Accept general types and return specific ones: take `Iterable[Passage]`, and return `list[Passage]`.
- Use `Protocol` for ports, so adapters don't need to inherit from a base class.
- Use `Literal` or `StrEnum` for fixed sets of values.

```python
# ❌ The reader has to guess, and so does mypy
def search(q, opts=None):
    ...

# ✅
def search(query: str, options: SearchOptions | None = None) -> list[SearchResult]:
    ...
```

**Don't**
- Use `Any` to get past an error. If a type is truly unknown, use `object` and narrow it with `isinstance`.
- Use `cast` unless a comment explains why the checker cannot know the type.

**Why:** The engine moves data between many layers. Types catch mismatches when the code is written, rather than in a user's run.

---

## Choosing a data type

| Use | When |
|-----|------|
| `@dataclass(frozen=True, slots=True)` | Domain values inside the engine, such as `Passage` |
| Pydantic `BaseModel` | Anything crossing a boundary: API bodies, blueprints, connector responses, AI structured output |
| `TypedDict` | LangGraph state, which is a dictionary by design |
| `StrEnum` | Fixed values that are stored or sent as text |

**Don't**
- Pass plain `dict[str, Any]` between functions.
- Import Pydantic or framework types into `domain/`. `import-linter` blocks this. For example, a blueprint file is validated by a Pydantic model at the edge, then converted to the frozen dataclass `Blueprint` in `domain/`.

```python
# ❌ Any key can be missing or misspelled
def to_passage(row: dict[str, Any]) -> dict[str, Any]: ...

# ✅
@dataclass(frozen=True, slots=True)
class Passage:
    record_id: str
    text: str
    location: str
```

**Why:** Immutable values cannot change unexpectedly while they pass through async code. Validation belongs at the edge, so the inside of the system can trust its data.

---

## Functions and classes

**Do**
- Keep each function to one job. Consider extracting parts once it is longer than about 20 lines.
- Use keyword-only arguments when a call would otherwise be unclear: `def chunk(text: str, *, size: int, overlap: int)`.
- Return early rather than nesting.
- Use `pathlib.Path` for paths.

**Don't**
- Use mutable default arguments.
- Create a class that holds no state and has one method. Use a function.
- Add an abstraction for a single use, unless it marks a real boundary such as a connector or a store.

```python
# ❌ All callers share the same list
def add_tag(tag: str, tags: list[str] = []) -> list[str]: ...

# ✅
def add_tag(tag: str, tags: Sequence[str] = ()) -> list[str]:
    return [*tags, tag]
```

---

## Comments and docstrings

**Do**
- Write a one-line docstring for every public module, class and function. Add more only where behaviour is not obvious.
- Use comments to explain *why*: a constraint, a vendor quirk, or a decision.

**Don't**
- Restate what the code does.
- Leave AI prompts, or thinking notes, in comments.

```python
# ❌ Increment the counter
retries += 1

# ✅ Jira can return 429 during a burst, even under the documented rate.
retries += 1
```

---

## Imports

- Ruff sorts imports automatically.
- Use absolute imports: `from synapse_engine.domain.record import Record`.
- Import heavy libraries, such as `fastembed` and `onnxruntime`, inside the adapter that uses them. See [Startup time](./advanced-performance.md#startup-time).
- Respect the layering: `domain` imports nothing from other layers, `application` imports `domain`, and `adapters` and `api` point inward.

---

## Review checklist

- [ ] Ruff and strict mypy pass, and any suppression names its rule and a reason.
- [ ] Every function has full type hints, with no unexplained `Any` or `cast`.
- [ ] Boundary data uses Pydantic, and domain data uses frozen dataclasses.
- [ ] No plain dictionaries pass between functions, apart from LangGraph state.
- [ ] No mutable default arguments.
- [ ] Public names have docstrings, and comments explain why.
- [ ] Imports follow the layering rules.
