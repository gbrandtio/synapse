# 0007. Rely on stored data, and treat external access as optional

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Agents could be designed around live tools that query sources directly. However, users may be offline, without credentials, or with expired sessions, and many local models cannot call tools.

## Decision

Search, counting and workflows work on stored records. Exact counts come from a query on stored data, and state the last sync date. A Fetch step tries to refresh, then follows its setting: continue with last synced data and a note, or stop. An Agent step uses stored data by default, and is available only when the chosen model supports tools.

## Consequences

The product works fully offline and behaves predictably. Answers can be out of date, so the date is always shown.

## Alternatives considered

- **Live tools as the main path:** It fails whenever access is missing, and requires tool-capable models.
