# 0006. Use one record format with declared fields per source type

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

All sources must return structured data for agents, yet sources differ: Jira has comments and start dates, and a PDF has neither.

## Decision

Every record has common parts, plus a `fields` object defined per source type. Each field declares its type and use: filterable, embedded, or shown to the AI. Users choose what to capture from the source's real field list. Text fields and comments become passages linked to the record. Filter fields live in SQLite's `record_fields`, and are copied to LanceDB columns. Details are in [Connectors](../architecture/connectors.md#capturing-different-details-per-source).

## Consequences

New sources and fields need no pipeline changes, and adding a field does not recalculate existing embeddings. Filter columns are duplicated, and Phase 0 tests this with many fields.

## Alternatives considered

- **Fully separate tables per source:** Search across sources becomes complex.
- **All details in one text blob:** Filtering and exact counting would be impossible.
