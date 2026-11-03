# LangChain and LangGraph Performance

AI calls dominate Synapse's response time and cost. These rules reduce and speed them up.

---

## What to measure

For each run, record:

- **Time to first word**, which is what the user feels most.
- **Total time**, split by node.
- **Input and output tokens** per model call.
- **Number of AI calls** per question.

**Do**
- Show cost and token counts in the run history.
- Compare changes against the fixed test set, so a speed-up cannot silently reduce quality.

---

## Use fewer AI calls

**Do**
- Skip question rewriting when there is no chat history.
- Use local search and re-ranking first, because they cost no AI call.
- Retry a weak search once at most.
- Use the app's code rather than AI for anything deterministic, such as counting records, formatting, and checking citations.

```python
# ❌ An AI call to count stored records
answer = await model.ainvoke(f"How many of these are open? {records}")

# ✅ An exact query, with a clear date
count = await records.count(filters=filters)
```

---

## Streaming

**Do**
- Stream every user-facing answer with `stream_mode="messages"`, so words appear immediately.
- Pass `version="v2"`, which gives each chunk the same `type`, `ns` and `data` keys.
- Send progress through `stream_mode="custom"` and `get_stream_writer()`, such as "Searching your documents".
- Stop generation when the user cancels, or disconnects.

```python
async for chunk in graph.astream(
    inputs,
    config=config,
    stream_mode=["messages", "custom"],
    version="v2",
):
    if chunk["type"] == "messages":
        message, metadata = chunk["data"]
        if metadata.get("langgraph_node") == NODE_GENERATE and message.content:
            yield TextDelta(message.content)
    elif chunk["type"] == "custom":
        yield Progress(chunk["data"])
```

**Don't**
- Forward tokens from internal nodes, such as question rewriting, to the user. Filter by node.

---

## Token budgets

**Do**
- Fit context to a budget before calling the model, starting with the highest-ranked passages.
- Remove duplicates, and overlapping passages, before adding surrounding sections.
- Limit chat history, keeping recent turns.
- Set a maximum output length.

**Don't**
- Send everything found and rely on the provider to reject or cut it. Local models may silently drop the beginning of a long prompt, which can remove your instructions.

**Why:** Tokens cost money on cloud models, and time on local models. Extra passages can also make answers worse by distracting the model.

---

## Batching and caching

**Do**
- Use `abatch` with `max_concurrency` for repeated independent calls, such as extracting fields from many tickets.
- Reuse model objects instead of creating them per call.
- Cache the results of expensive repeated work by content hash.
- Use provider prompt caching where available, by keeping long stable text first in the prompt.

```python
results = await extractor.abatch(prompts, config={"max_concurrency": 4})
```

**Don't**
- Cache answers to user questions by default. The underlying documents change, so answers can go stale.

---

## Review checklist

- [ ] Each change is compared on the fixed test set, for both quality and speed.
- [ ] Deterministic work uses code rather than AI.
- [ ] Answers stream, and internal node tokens stay hidden.
- [ ] Cancelling stops generation.
- [ ] Context and output have token limits.
- [ ] Repeated calls are batched, with a concurrency limit.
