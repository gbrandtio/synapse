# LangChain and LangGraph Coding Standards

How graph and model code should look in Synapse.

---

## Where code lives

- `adapters/ai/` holds all imports of `langchain` and `langgraph`.
- `adapters/ai/graphs/` holds graph builders, with one file per graph.
- `adapters/ai/nodes/` holds node functions.
- Domain types never contain LangChain messages or LangGraph objects.

```python
# ❌ A framework type leaks into the domain
from langchain_core.messages import AIMessage

@dataclass
class Answer:
    message: AIMessage

# ✅ The adapter converts it
@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    citations: tuple[Citation, ...]
```

---

## Naming

| Thing | Style | Example |
|-------|-------|---------|
| Graph builder | `build_<name>_graph` | `build_answer_graph` |
| Node function | Verb phrase | `rewrite_question`, `rerank_passages` |
| Node name in the graph | Same as the function, as a constant | `NODE_RERANK = "rerank_passages"` |
| Routing function | `route_after_<node>` | `route_after_grade` |
| State type | `<Graph>State` | `AnswerState` |

**Don't**
- Scatter node names as string literals. A typo creates a runtime error.

---

## State

**Do**
- Define state as a `TypedDict`, with the fewest fields possible.
- Annotate fields that accumulate with a reducer.
- Keep state JSON-friendly: IDs, text, numbers, and small dictionaries.

```python
class AnswerState(TypedDict):
    question: str
    standalone_question: str
    passages: list[PassageData]
    retries: int
    messages: Annotated[list[AnyMessage], add_messages]
```

**Don't**
- Put clients, connections, models, or secrets in state. State gets written to checkpoints.
- Store large content when an ID will do.

**Why:** Everything in state is saved to disk in every checkpoint, which costs time and could expose secrets.

---

## Nodes

**Do**
- Make each node do one job, and return only the keys it changes.
- Fully type each node's input and output.
- Inject dependencies when building the graph, through closures or runtime context.

```python
# ❌ A global client, and a mutated input
def search(state: AnswerState) -> AnswerState:
    state["passages"] = GLOBAL_INDEX.search(state["question"])
    return state

# ✅
def make_search_node(index: SearchIndex) -> Callable[[AnswerState], Awaitable[dict[str, object]]]:
    async def search_knowledge(state: AnswerState) -> dict[str, object]:
        passages = await index.search(state["standalone_question"])
        return {"passages": [p.as_data() for p in passages]}

    return search_knowledge
```

---

## Prompts

**Do**
- Keep built-in prompts in versioned text files, not inside functions.
- Fill user-editable prompts with Synapse's own single-pass replacer. See [ADR 0012](../adr/0012-safe-prompt-filling.md).
- Keep source text separate from instructions, wrapped and labelled as data.

**Don't**
- Use f-strings, `str.format`, or Jinja templates on content or user prompts.
- Put model IDs in code. They come from the model catalog file.

```python
# ❌ Source text can look like instructions, and braces can break formatting
prompt = f"Answer using this: {ticket_text}"

# ✅
prompt = fill_template(user_prompt, {"question": question, "results": as_untrusted(passages)})
```

---

## Tools and structured output

**Do**
- Write tool names and descriptions for the model to read: say what the tool does, and when to use it.
- Give tool inputs a Pydantic model with clear field descriptions.
- Return structured records as JSON, with `completeness` included.
- Use a Pydantic model for structured output, and validate the values after the model responds.

**Don't**
- Give a tool a broad input such as free-form SQL or a URL.
- Assume a local model can use tools or structured output. Synapse tests the selected model first.

---

## Review checklist

- [ ] LangChain and LangGraph imports stay in `adapters/ai/`.
- [ ] Node names are constants, and nodes return only what they change.
- [ ] State holds small, JSON-friendly values, and no clients or secrets.
- [ ] Prompts avoid f-strings and Jinja, and label source text as data.
- [ ] Model IDs come from the catalog.
- [ ] Tools have narrow, typed inputs and clear descriptions.
