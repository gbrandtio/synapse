# 0014. Support English only, on Windows and macOS only

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Supporting many languages forced larger models. The only small multilingual re-ranker FastEmbed offers is about 570 MB, which does not fit the size budget in [ADR 0010](./0010-bundled-models-and-github-limits.md). Each extra operating system also adds builds, tests and packaging work.

## Decision

The bundled models are chosen for English, and the app's interface is English only. Releases are built for Windows and macOS only.

## Consequences

Small English models fit the budget, and there is one test set to tune. Documents and questions in other languages may return poor results, and Synapse makes no promise about them. A cloud or larger local model may still answer in other languages, but retrieval still uses the English embedding model. Linux users are not served. Adding either later means re-testing models or adding a build, and changing the embedding model means reprocessing every collection.

## Alternatives considered

- **Multilingual models:** They cost several hundred MB more, leaving less room for the AI model.
- **Including Linux:** It adds a build and more packaging formats, and needs a separate plan for systems with no keychain service.
