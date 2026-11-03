# FastAPI Coding Standards

How API code should look in Synapse.

---

## Thin routes

**Do**
- Use one `APIRouter` per feature, in `api/routes/`.
- Limit each route to validating, calling a use case, and converting the result.

```python
# ❌ Business logic in the route
@router.post("/collections/{collection_id}/sync")
async def sync(collection_id: str) -> dict[str, str]:
    sources = await db.fetch_sources(collection_id)
    for source in sources:
        ...

# ✅
@router.post("/collections/{collection_id}/sync", status_code=202)
async def start_sync(
    collection_id: CollectionId,
    use_case: Annotated[StartSync, Depends(get_start_sync)],
) -> JobResponse:
    job = await use_case.run(collection_id)
    return JobResponse.from_domain(job)
```

**Why:** Thin routes keep the logic testable without HTTP, and reusable if the API layer changes.

---

## Paths and naming

| Rule | Example |
|------|---------|
| Plural nouns | `/collections`, `/assistants` |
| Nested only when owned | `/collections/{collection_id}/sources` |
| Actions as sub-resources, only when CRUD doesn't fit | `POST /collections/{id}/sync` |
| `snake_case` in JSON and query parameters | `collection_id`, `updated_at` |
| A version prefix | `/api/v1/...` |
| Stable `operation_id` | `start_collection_sync` |

Set a clear `operation_id` on each route, because the generated Dart client uses it for method names.

---

## Request and response models

**Do**
- Define a separate Pydantic model for each request and response, named `<Thing>Request` and `<Thing>Response`.
- Use `Annotated` for dependencies and parameter constraints.
- Declare return types, so that FastAPI validates and documents responses.
- Set `extra="forbid"` on request models, so typos give errors rather than being ignored.
- Add limits to strings and lists.

```python
class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Annotated[str, Field(min_length=1, max_length=8000)]
    collection_ids: Annotated[list[str], Field(max_length=50)] = []
```

**Don't**
- Return domain objects directly, or accept or return plain `dict`.
- Share one model between requests and responses to save time.
- Use `Any` in a model, because it produces an unusable type in the Dart client.

---

## OpenAPI as the contract

**Do**
- Export `openapi.json` to `contracts/` as part of the build, and regenerate the Dart client from it.
- Fail CI if the committed file differs from the generated one.
- Document error responses with `responses=`, so the client knows their shape.
- Add a short description to fields shown in the UI.

**Don't**
- Hand-edit generated client code.
- Make a breaking change within `/api/v1` once it has shipped to users.

---

## Review checklist

- [ ] Routes contain no business logic.
- [ ] Each route has a typed request, response and stable `operation_id`.
- [ ] Request models forbid unknown fields, and limit sizes.
- [ ] `contracts/openapi.json` matches, and the Dart client has been regenerated.
- [ ] Error responses are documented.
