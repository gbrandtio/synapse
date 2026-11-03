# LangChain and LangGraph Guidelines

How the Synapse engine uses LangChain and LangGraph. General Python rules are in [Python Guidelines](../python/index.md).

**Baseline:** `langchain` 1.4 · `langgraph` 1.2 · `langgraph-checkpoint-sqlite` 3.1. These libraries change quickly, so check the [official docs](https://docs.langchain.com/oss/python/langgraph/overview) when upgrading.

## Contents

| Page | What it covers |
|------|----------------|
| [Coding Standards](./coding-standards.md) | Naming, state, nodes, prompts, tools, and where code lives. |
| [Best Practices](./best-practices.md) | Graph design, checkpoints, interrupts, agents, model handling, prompt-injection defence, and testing. |
| [Performance](./performance.md) | Streaming, token budgets, batching, and reducing AI calls. |
| [Advanced Performance](./advanced-performance.md) | Durability modes, checkpoint size, local model behaviour, parallel branches, and tracing. |

## How we use each library

| Library | Used for |
|---------|----------|
| LangChain | Model access (`init_chat_model`), `create_agent` for the Agent step, messages, and structured output |
| LangGraph | The answer pipeline, and compiled workflows with checkpoints and approvals |

These libraries stay in `adapters/ai/`. Domain and application code depend on Synapse's own interfaces, so a library upgrade stays contained.

## Precedence

1. Tests and static checks enforced by CI.
2. Accepted [ADRs](../adr/README.md).
3. These guidelines.
4. Personal preference.
