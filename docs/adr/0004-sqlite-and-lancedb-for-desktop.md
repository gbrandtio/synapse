# 0004. Use SQLite and LanceDB on desktop, and PostgreSQL later for teams

- Status: Accepted. The LanceDB part is replaced by [ADR 0015](./0015-sqlite-vec-and-fts5-as-search-store.md)
- Date: 2026-11-03
- Deciders: Project owner

## Context

Synapse needs storage for records, jobs, checkpoints and a search index. PostgreSQL with pgvector could technically do all of this in one database. The main goal, however, is an installer that needs no setup.

## Decision

Desktop uses SQLite for records and app data, and LanceDB for the search index. Both run inside the engine process with no server. Team server mode, when it arrives, uses PostgreSQL with pgvector. Storage sits behind interfaces, so that change stays contained. Nothing for PostgreSQL is built now. Phase 0 also compares LanceDB with SQLite plus `sqlite-vec`, which could reduce this to one file.

## Consequences

Users have no database server to run, start, or upgrade. The costs are two storage engines, filter fields copied between them, and a migration when team mode arrives.

## Alternatives considered

- **PostgreSQL on desktop:** It would need bundling, a port, process management, and major-version upgrades on every computer.
- **Chroma:** Sources disagree about its self-hosted hybrid search, and most describe it as cloud-first.
