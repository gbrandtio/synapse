# Workflows, agents and prompts

**Phase 1 status:** no workflow steps are built yet. This page describes the Phase 5 design. Where a rule is already built in Phase 1, the text says so.

Each assistant blueprint compiles into a LangGraph graph, so a future canvas can edit the same file without changing the engine.

| Step | Blueprint `type` | Purpose | User's own prompt |
|---|---|---|---|
| Trigger | `trigger` | Manual, on a schedule, or when a collection changes | No |
| Fetch | `fetch` | Refresh records from a connector if available. If unreachable, it either uses the last synced data and notes this, or stops, according to its setting | No |
| Search knowledge | `search_knowledge` | Run RAG retrieval on chosen collections | Optional, to reword the search |
| Query records | `query_records` | List or count stored records using a simple filter form | No |
| Ask AI | `ask_ai` | Send a prompt with earlier steps as input | **Yes** |
| Extract data | `extract_data` | Return structured output, defined with a simple field form | **Yes** |
| Agent | `agent` | Let the AI repeatedly choose among allowed actions | **Yes** |
| If | `if` | Branch on a condition, either a rule or an AI yes/no question | **Yes**, for the AI question |
| Ask me first | `approval` | Pause for approval, using LangGraph `interrupt` | No |
| Output | `output` | Chat reply, Markdown file, or clipboard | No |

Starter templates: **Ask my documents**, **Codebase helper**, **Jira weekly digest**, **Release notes from GitHub**, **Ticket triage suggestions**. None of them requires an Agent step.

**Agent step:** it only uses what is actually available. Its default actions are Search knowledge and Query records, on stored data. A connector's Fetch can be added as an action if that connection exists. Not every model supports tool calling, so Synapse tests the selected model and, if it cannot, explains this and offers a compatible model or a template without an Agent step.

SQLite checkpoints let runs survive restarts and wait for approval. Scheduled runs only happen while the app is running.

## Custom prompts

Users can write their own prompt in every AI step. Templates only supply a starting point, which is always visible and editable.

- **Variables:** a prompt can use `{{question}}`, `{{today}}`, `{{steps.search.results}}` and `{{steps.fetch.records}}`. The editor inserts them as clickable chips, so nobody has to memorise the syntax. Unknown variables are flagged before running.
- **Trying it:** "Test this step" runs that one prompt on sample data and shows the exact text sent to the AI, its token count, and the result.
- **History:** each edit is saved, so users can compare versions, undo a change, or reset to the template's original.
- **Prompt library:** users can save a prompt and reuse it in other steps and assistants.
- **RAG's internal prompts:** the question rewording and result checking prompts are editable in Expert mode.

Three protections stay active whatever a user writes:

- **Safe filling:** variables are filled by a small, single-pass replacer, and not by Jinja or Python format strings. A ticket that contains `{{...}}` therefore stays as plain text and cannot run code or insert another variable.
- **Untrusted content:** text from sources is automatically wrapped and labelled as data when inserted. A short safety instruction is added outside the user's prompt, and the user can read it. This means a custom prompt cannot accidentally remove the protection against harmful content. Phase 1 already wraps each passage in a `<passage>` tag and escapes its text. See [RAG pipeline](./rag-pipeline.md#answering-a-question).
- **System-enforced citations:** the Show sources setting is enforced by the app rather than by prompt wording, so rewriting a prompt does not lose source links. Phase 1 already does this. When the AI cites nothing, the best passage is shown as a "Likely source".

An imported `.synapse` file came from someone else, so nothing in it runs until the user has reviewed it. A review screen shows its prompts, AI provider and endpoint, sources, and any hosts it may reach. Each new endpoint, local folder, or host must be confirmed individually, and a custom AI endpoint is called out clearly, because retrieved passages would be sent to it.

## Security against harmful content

Documents, tickets and web pages may contain instructions written to manipulate the AI, and this is the main risk in the design.

- Fetched content is labelled as untrusted data in prompts, and is never treated as instructions.
- All actions are **read-only** in the first release, so a poisoned ticket cannot make the agent change anything.
- Any future step with side effects must pass "Ask me first".
- Fetch actions can only reach hosts configured for that assistant.
- The answer view never auto-loads remote images or links, which closes a common way of leaking data.
- Each run has limits on steps, time and spending.

## Sources

- LangGraph: [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- LangChain: [agents](https://docs.langchain.com/oss/python/langchain/agents), [built-in middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)

Coding guidance for these libraries is in [LangChain and LangGraph best practices](../langchain/best-practices.md).
