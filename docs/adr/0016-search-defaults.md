# 0016. Set search defaults from measured results

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

The plan used balanced hybrid search with re-ranking always on. [Phase 0](../phase0/results.md#search-quality) found that equal weighting lowers scores, and re-ranking did not clearly help.

## Decision

The embedding model is `bge-small-en-v1.5`. Hybrid search stays, with a keyword weight of 0.1, raised to 1.0 when a short question looks like an exact term, such as `ERR_TIMEOUT_504`. Re-ranking `Xenova/ms-marco-MiniLM-L-6-v2` stays available, is off by default, and checks only the top 12 results when on.

## Consequences

Answers come faster, and exact terms still work. The test set is small and the rule was tuned on it, so Phase 2 retests on new questions in a realistic-size index. The re-ranking default may change as a result. Moving to a better embedding model later means reprocessing every collection.

## Alternatives considered

- **Vector search only:** It missed one exact ticket term in ten, and may do worse in a large index.
- **`bge-base-en-v1.5`:** Slightly better, but three times larger and three times slower to index.
