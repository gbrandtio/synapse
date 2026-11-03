# Architecture Decision Records

Each record explains why a significant decision was made. Records are never deleted: a newer one supersedes them. The format follows [Architecture Principles](../dotnet/architecture-principles.md#architecture-decision-records-adrs).

| ADR | Decision |
|---|---|
| [0001](./0001-python-engine.md) | Use a Python engine for all AI work |
| [0002](./0002-desktop-sidecar.md) | Run the engine as a local sidecar process |
| [0003](./0003-bloc-state-management.md) | Use Bloc for Flutter state |
| [0004](./0004-sqlite-and-lancedb-for-desktop.md) | Use SQLite and LanceDB on desktop, and PostgreSQL later for teams |
| [0005](./0005-one-rag-pipeline-with-collections.md) | Use one RAG pipeline and index, with named collections |
| [0006](./0006-record-and-field-model.md) | Use one record format with declared fields per source type |
| [0007](./0007-stored-data-over-live-access.md) | Rely on stored data, and treat external access as optional |
| [0008](./0008-access-methods-per-source.md) | Define access methods per source |
| [0009](./0009-spreadsheet-import.md) | Import Jira details from Excel and CSV as normal records |
| [0010](./0010-bundled-models-and-github-limits.md) | Bundle Ollama and models within GitHub's release limits |
| [0011](./0011-read-only-actions.md) | Keep all actions read-only in the first release |
| [0012](./0012-safe-prompt-filling.md) | Fill prompt variables with a single-pass replacer |
| [0013](./0013-unsigned-first-builds.md) | Ship first builds without code signing |
| [0014](./0014-english-only-windows-and-mac.md) | Support English only, on Windows and macOS only |
| [0015](./0015-sqlite-vec-and-fts5-as-search-store.md) | Use sqlite-vec and FTS5 as the search store |
| [0016](./0016-search-defaults.md) | Set search defaults from measured results |
| [0017](./0017-bundled-ai-model.md) | Bundle Gemma 3 1B as the offline AI model |
