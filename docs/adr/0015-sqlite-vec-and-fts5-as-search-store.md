# 0015. Use sqlite-vec and FTS5 as the search store

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

[ADR 0004](./0004-sqlite-and-lancedb-for-desktop.md) chose LanceDB and asked Phase 0 to compare it with SQLite plus `sqlite-vec`. [The results](../phase0/results.md#search-store) show sqlite-vec is fast enough at desktop sizes.

## Decision

The search index lives in the same SQLite file as records. Vectors use a `vec0` table, keywords use FTS5, and filters use ordinary tables through `id IN (subquery)`. Results are merged with weighted Reciprocal Rank Fusion in SQL. The `sqlite-vec` version is pinned, and everything stays behind the storage interface.

## Consequences

There is one file to back up, and one transaction covers records and vectors, so a failed sync cannot leave them out of step. The installer shrinks by about 290 MB before compression. Search is exact, so it never misses a result the way an approximate index can.

Search time grows in step with size: about 120 ms at 300,000 passages, and an estimated 400 ms at 1,000,000. sqlite-vec is pre-1.0, and Windows is not yet tested. FTS5 keyword filters must use a join, because `rowid IN (subquery)` is very slow.

## Alternatives considered

- **LanceDB:** About six times faster at 100,000 passages, but it means two stores, data copied between them, and about 290 MB more. Its approximate index also needs tuning.
