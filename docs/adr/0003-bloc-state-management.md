# 0003. Use Bloc for Flutter state

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

The UI has long-running, event-driven flows: chat streaming, sync jobs, and workflow runs. It needs predictable state that is easy to test.

## Decision

All feature state uses `flutter_bloc`. `Bloc` is used for event-driven flows, and `Cubit` for simple state. `bloc_concurrency` sets the behaviour per event, and `bloc_test` tests every bloc. Rules are in [docs/bloc](../bloc/index.md).

## Consequences

State changes are explicit and easy to test, and event concurrency is declared rather than hand-written. There is more boilerplate than with lighter options.

## Alternatives considered

- **Riverpod:** It is also widely used and testable, but the project owner chose Bloc for its explicit events.
