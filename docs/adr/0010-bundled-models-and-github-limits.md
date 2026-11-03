# 0010. Bundle Ollama and models within GitHub's release limits

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Users should be able to work offline from first launch. Releases are hosted on GitHub, where each release file must be under 2 GiB, while total release size and bandwidth are unlimited. Files in the git repo get a warning above 50 MiB, and LFS has quotas.

## Decision

There are two downloads. Complete includes Ollama, a small AI model, and the embedding and re-ranking models. Standard leaves out Ollama and the AI model, and serves cloud users and updates. Models live only in release assets, pinned by hash and licence in `packaging/models.lock.yaml`. CI fails above 1.9 GiB. The bundled model must allow redistribution, handle multiple languages, and produce reliable structured output.

## Consequences

About 550 MB to 1 GB remains for the AI model below the 1.9 GiB CI limit (estimated), so it will be a small one: fine for answering from passages, and weaker at complex reasoning. Complete stays one file, as the project owner decided, so first answers may be weaker than a larger model would give. Phase 0 picks the best model that fits, and the first screen offers larger models and cloud AI. If no candidate is acceptable, the decision returns to the project owner.

## Alternatives considered

- **Download models on first run:** It fails the offline-from-first-launch goal.
- **Complete as an installer plus a model pack:** It would allow a 2 to 3 GB model and better answers, but users would have to download two files and keep them together.
- **Git LFS:** It has quotas and offers no benefit over release assets.
- **Hosting on another service:** It adds a dependency while GitHub's limits are workable.
