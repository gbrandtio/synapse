# 0017. Bundle Gemma 3 1B as the offline AI model

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner
- Note (2026-11-03): the model is now a Gemma 3 1B GGUF file served by the llama.cpp server, not by Ollama. See [ADR 0018](./0018-llama-cpp-instead-of-ollama.md).

## Context

Complete must carry one small AI model. [Phase 0](../phase0/results.md#bundled-ai-model) tested five candidates.

## Decision

Complete bundles `gemma3:1b`. It had the best answers, extraction and filters, and it fits the budget. The model list stays a data file, so swapping the model needs no code change.

## Consequences

**Licence:** Gemma is not Apache or MIT. Redistribution is allowed if Synapse includes the use restrictions in its own terms, gives users a copy of the agreement, and ships the required notice file. Licence scanning must allow this model explicitly.

**No tool calling:** the bundled model cannot run an Agent step. Synapse explains this and offers a compatible model. No starter template needs an Agent step.

It is still a small model, weaker at complex reasoning, so the first screen offers larger models and cloud AI.

## Alternatives considered

- **`qwen2.5:1.5b`:** Apache licence and tool calling, but it is 171 MB larger, scored 2 of 4 on filters, and sometimes answered with only a citation. It is the first choice if the Gemma terms are unacceptable.
- **`granite4:350m`:** Apache licence, but slow at 23 tokens per second in this test.
- **`qwen3:0.6b`:** It obeyed a prompt-injection attempt.
