# Advanced LangChain and LangGraph Performance

For when [Performance](./performance.md) is not enough. Use these only after measuring.

---

## Durability modes

Each run sets how carefully checkpoints are saved.

| Mode | Behaviour | Use for |
|------|-----------|---------|
| `"exit"` | Saves only when the run ends, errors, or reaches an interrupt. A crash loses progress | Short chat answers, which can simply be asked again |
| `"async"` | Saves in the background while the next step runs. A crash can lose recent checkpoints | Most multi-step runs |
| `"sync"` | Saves before the next step starts. Most durable, and somewhat slower | Workflows with approvals, or expensive steps |

**Do**
- Use `"exit"` for chat, and `"sync"` for workflows that must survive restarts.
- Record that a run was accepted in Synapse's own jobs table. With `"async"` or `"exit"`, a crash can happen before any checkpoint exists, and resuming then raises `EmptyInputError`.

---

## Keeping checkpoints small

Each step's state gets saved, so large state slows each step and grows the database.

**Do**
- Store passage IDs and scores in state, and load the text when building context.
- Clear intermediate fields once they are no longer needed.
- Delete checkpoints for old finished runs on a schedule.
- Measure checkpoint size per run in tests, and alert on sudden growth.

**Don't**
- Put full records or whole documents in state.

---

## Parallel branches

**Do**
- Run independent work in parallel with fan-out edges, or `Send` for a variable number of items.
- Use reducers on any field written by several branches.
- Limit parallelism with the `max_concurrency` config value.

```python
class ExtractState(TypedDict):
    record_ids: list[str]
    extracted: Annotated[list[ExtractedData], operator.add]

def fan_out(state: ExtractState) -> list[Send]:
    return [Send(NODE_EXTRACT_ONE, {"record_id": record_id}) for record_id in state["record_ids"]]
```

**Don't**
- Search once per collection and join the lists. Synapse runs one search filtered by collection ID, so that scores compare fairly ([ADR 0005](../adr/0005-one-rag-pipeline-with-collections.md)).
- Run several local AI calls in parallel without measuring. Local models often process requests one at a time, or need far more memory to do otherwise.

---

## Local model behaviour

Local models have their own costs, which differ from cloud AI.

**Do**
- Pre-load the model when the user opens a chat, so the first question avoids the load delay.
- Set the context window (`num_ctx`) deliberately. Larger windows use more memory, and a too-small window can silently cut off the prompt.
- Keep the prompt prefix stable, so that the model can reuse work between requests where supported.
- Unload the model when idle, using `keep_alive`, so that memory returns to the user's computer.
- Give the user's question priority over background extraction jobs.

**Don't**
- Assume a small model handles agent loops well. Limit the steps, and test tool calling and structured output for each bundled or recommended model.
- Copy cloud token budgets to local models without measuring. A local model may need a much smaller context to stay responsive.

---

## Tracing and diagnostics

**Do**
- Log timings and token counts for each node, using Synapse's own run records.
- Use `stream_mode="tasks"` or `"checkpoints"` in development to inspect what a run does. Both need a checkpointer.
- Use `get_state_history` to investigate failed runs.
- Enable LangSmith only in development, with test data.

**Don't**
- Log prompts or source text in production logs.

---

## Review checklist

- [ ] The durability mode is chosen deliberately, and accepted runs are recorded separately.
- [ ] State holds IDs instead of large content, and old checkpoints get cleaned up.
- [ ] Parallel branches have reducers and concurrency limits.
- [ ] Local AI settings (`num_ctx`, `keep_alive`) are set deliberately and measured.
- [ ] Tracing to external services is off in release builds.
