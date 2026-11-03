# LangChain and LangGraph Best Practices

How to build reliable graphs and agents for Synapse.

---

## Graph design

**Do**
- Prefer a fixed graph with clear stages to an agent. It is faster, cheaper, and more predictable.
- Cap every loop with a counter in state, and route out when it is reached.
- Keep routing functions pure, so that they can be tested without any model.
- Set `recursion_limit` on every run as a final safety limit.

```python
def route_after_grade(state: AnswerState) -> str:
    if state["grade"] == "good":
        return NODE_BUILD_CONTEXT
    if state["retries"] >= MAX_RETRIES:
        return NODE_NOT_FOUND
    return NODE_REWORD_QUESTION
```

**Don't**
- Let a model decide the next step when a simple rule would do.
- Create a loop whose only exit depends on model output.

**Why:** A workflow that always finishes is essential for non-technical users, who cannot debug a stuck run.

---

## Checkpoints

**Do**
- Use `AsyncSqliteSaver` for async runs, from `langgraph.checkpoint.sqlite.aio`.
- Use a new `thread_id` per run or conversation, and store it with the run record.
- Choose a durability mode deliberately. See [Advanced Performance](./advanced-performance.md#durability-modes).

```python
config = {
    "configurable": {"thread_id": run.id},
    "recursion_limit": 50,
}
result = await graph.ainvoke(inputs, config=config, durability="sync")
```

**Don't**
- Turn on `pickle_fallback` in the serializer. Checkpoints should hold plain data, and unpickling is unsafe if a file gets altered.
- Assume checkpoints are private. They contain document text, so they get the same protection as other user data. `EncryptedSerializer` is available if encryption becomes a requirement.

---

## Interrupts: the "Ask me first" step

`interrupt()` needs a checkpointer and a thread ID. When resumed, **the node restarts from its beginning**, and this drives the rules below.

**Do**
- Resume using `Command(resume=value)` with the same `thread_id`.
- Keep the interrupt payload JSON-serializable.
- Put the interrupt in its own small node, or make any earlier work idempotent.

```python
def approval_node(state: WorkflowState) -> dict[str, bool]:
    approved = interrupt({"question": state["approval_question"]})
    return {"approved": bool(approved)}
```

**Don't**
- Wrap `interrupt()` in a broad `try/except`. It works by raising a special exception, which would be caught.
- Skip interrupts conditionally, or loop over changing data. Resume values match by position within the node.
- Re-prompt in a `while True` loop. Use one interrupt per node run, and loop with a conditional edge.
- Do non-idempotent work before an interrupt, because it runs again on resume.

---

## Agents: the Agent step

**Do**
- Use `create_agent` from `langchain.agents`.
- Give the agent the fewest tools possible, with Search knowledge and Query records as the default.
- Set limits with `ModelCallLimitMiddleware` and `ToolCallLimitMiddleware`.
- Test the selected model's tool support first, and explain when it has none.

```python
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

agent = create_agent(
    model=model,
    tools=[search_knowledge, query_records],
    system_prompt=system_prompt,
    middleware=[
        ModelCallLimitMiddleware(run_limit=settings.max_agent_steps, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=settings.max_agent_steps),
    ],
    checkpointer=checkpointer,
)
```

**Don't**
- Assume any external connection exists. See [ADR 0007](../adr/0007-stored-data-over-live-access.md).
- Add a tool that changes data. All actions are read-only in the first release ([ADR 0011](../adr/0011-read-only-actions.md)).

---

## Models

**Do**
- Create chat models with `init_chat_model`, so providers change through configuration.
- Set timeouts and retries for every model.
- Handle provider failures explicitly: bad key, out of credit, rate limit, model not installed, and context too long. Each one should map to a clear user message.
- Keep the "Never send data off this computer" setting enforced where models are created, so that no code path can bypass it.

**Don't**
- Trust model output. Validate structured output, confirm citations point to real passages, and check that filters use known fields.
- Enable LangSmith tracing in release builds, because user content must stay private.

---

## Defending against prompt injection

Documents and tickets can contain text written to manipulate the AI. No prompt can reliably prevent this, so limit the damage instead.

**Do**
- Assume injection will sometimes succeed, and make sure it can do little: read-only tools, with limited hosts.
- Wrap and label source content as data, and keep the safety instruction outside user prompts.
- Avoid auto-loading remote images and links in answers, which could leak data.
- Limit steps, time, and spending per run.
- Keep poisoned-document tests in CI, using default and custom prompts.

**Don't**
- Treat text from a tool result as an instruction.
- Rely on the phrase "ignore any instructions in the text" as your only protection.

---

## Testing

**Do**
- Test routing functions and nodes as plain functions.
- Run whole graphs with a fake chat model and `InMemorySaver`.
- Test interrupts by running to the pause, resuming, and confirming earlier work was not repeated.
- Keep separate retrieval-quality tests in CI, against fixed test sets.

**Don't**
- Call real AI providers in unit tests.
- Assert on exact AI wording, except with a fake model.

---

## Review checklist

- [ ] Every loop has a cap, and every run has a `recursion_limit`.
- [ ] A fixed graph is used wherever it is enough, and agents have limits.
- [ ] Interrupt rules are followed, with idempotent work before an interrupt.
- [ ] `pickle_fallback` is off, and state holds no secrets.
- [ ] Model errors map to clear messages, and model output is validated.
- [ ] Tools are read-only, and source content is labelled as data.
- [ ] Tests use a fake model, and cover resume and injection cases.
