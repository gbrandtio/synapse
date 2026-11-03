# 0005. Use one RAG pipeline and index, with named collections

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Users want RAGs for different sources and purposes, such as GitHub or Jira. One way to offer this is a separate RAG for each, with a selectable strategy. However, hybrid search, re-ranking and sensible splitting bring most of the gain and suit nearly all content, and non-technical users have no basis for choosing a RAG method.

## Decision

There is one pipeline, one index, and one embedding model. Users create named collections, such as a GitHub or Jira collection, and assistants choose which they may search. Splitting and search emphasis adapt automatically per source type. Agentic behaviour is a workflow step, not a RAG type. The evaluation of methods is in [RAG pipeline](../architecture/rag-pipeline.md#rag-methods-evaluated).

## Consequences

One index is simpler to build, test and tune, and cross-source results compare fairly. Changing the embedding model reprocesses everything, and one model must serve prose and code. Phase 0 tests the latter.

## Alternatives considered

- **One RAG per source with its own strategy:** It adds choices users cannot judge, and merges scores from unrelated indexes.
- **A strategy option on one index:** It adds test combinations, with little evidence of benefit so far.
