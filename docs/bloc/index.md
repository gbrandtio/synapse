# Bloc Guidelines

How Synapse's Flutter app manages state with Bloc. These pages add to the general Flutter and Dart rules in [docs/flutter](../flutter/CODING_STANDARDS.md), which still apply: `Result<T>`, no `dynamic`, and full test coverage.

**Baseline:** `bloc` 9 · `flutter_bloc` 9 · `bloc_concurrency` 0.3 · `bloc_test` 10.

## Contents

| Page | What it covers |
|------|----------------|
| [Coding Standards](./coding-standards.md) | Naming, events, states, and file layout. |
| [Best Practices](./best-practices.md) | Bloc or Cubit, layering, side effects, provider scope, errors, and testing. |
| [Performance](./performance.md) | Rebuild control, `buildWhen`, selectors, and equality. |
| [Advanced Performance](./advanced-performance.md) | Event transformers, streaming answers, throttling, Isolates, and diagnosing rebuilds. |

## Why Bloc

See [ADR 0003](../adr/0003-bloc-state-management.md). In short, Synapse's UI has long-running, event-driven flows, and Bloc makes those flows explicit and easy to test.

## Precedence

1. `dart analyze`, `dart format`, and tests enforced by CI.
2. Accepted [ADRs](../adr/README.md).
3. These guidelines.
4. Personal preference.
