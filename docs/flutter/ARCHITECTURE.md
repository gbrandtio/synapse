# RwGit Architecture

This document describes the refactored architecture of the `rw_git` package, adhering to the project's coding standards.

## 1. Core Principles

- **Separation of Concerns**: Parsing, execution, and strategy logic are strictly decoupled.
- **Security by Default**: All OS process execution is done without a shell (`runInShell: false`) to prevent command injection, adhering to `SECURITY.md`.
- **Concurrency**: High-cpu/blocking tasks, such as regex parsing and log processing, are offloaded to background threads using Dart's `Isolate.run()`, ensuring the main event loop remains responsive as per `DART_PERFORMANCE_AND_CONCURRENCY.md`.
- **Testability**: Process execution is abstracted behind a `ProcessRunner` interface, enabling deterministic unit testing via `MockProcessRunner`.

## 2. Components

### 2.1 Facade (`RwGit`)
The `RwGit` class serves as the primary entry point for consumers. It is a Facade that provides a simplified, high-level API over complex Git commands. It delegates actual work to specific Command Strategy implementations.

### 2.2 Process Runner (`ProcessRunner`)
Instead of calling `Process.run` directly everywhere, `rw_git` uses a `ProcessRunner` interface.
- **`StandardProcessRunner`**: The default implementation for production. It safely executes standard OS processes and parses exit codes.
- **`MockProcessRunner`**: Used for unit tests. It allows developers to mock standard output, standard error, and exit codes for specific commands.

### 2.3 Command Strategies (`GitCommand<T>`)
Every Git operation is implemented as an encapsulated strategy extending `GitCommand<T>`. This allows the addition of new commands without modifying the core facade. Examples include:
- `CloneCommand`
- `StatsCommand`
- `FetchTagsCommand`

### 2.4 Intelligence Layer (`lib/src/intelligence/`)
The research-backed analyses. Each algorithm or heuristic takes a `ProcessRunner` and returns a strongly-typed DTO from `lib/src/models/`, so the same analysis is usable as a plain Dart API or behind an MCP tool. CPU-bound parsing of large git outputs is offloaded to Isolates (ADR-0003).
- **`architecture/`**: Bus factor, logical coupling, refactoring detection, and architecture drift.
- **`history/`**: SZZ bug attribution and code volatility (`algorithms/`); bug hotspots, churn, commit velocity, advanced metrics, mega commits, and suspicious commits (`heuristics/`).
- **`security/`**: Secrets scanning, commit compliance, dependency manifest parsing, and dependency freshness checks.
- **`static_analysis/`**: Language-agnostic lexical metrics on an FSM lexer (`metrics/`), clean-code heuristics, and Dart AST analysis (`dart/`).
- **`interpretation/`**: Severity classifiers per analysis, compound-finding correlation, and refactoring-target ranking that turn raw metrics into classified findings server-side (ADR-0005, ADR-0017).

### 2.5 MCP Server (`bin/rw_git_mcp.dart`, `lib/src/mcp/`)
An implementation of the Model Context Protocol (MCP) using a standard I/O JSON-RPC loop.
- **Request dispatch**: Each JSON-RPC method is handled by a dedicated rule in `mcp_server/rules/` (ADR-0008).
- **Tools**: 30+ tools grouped by category under `tools/` (`architecture`, `core`, `history`, `reports`, `security`, `static_analysis`, `system`) and registered in `server_registry.dart` (ADR-0009).
- **Decorators**: `McpToolWithMetadata` (ADR-0002), `McpToolHintsDecorator`, and `McpToolFileOffloadDecorator`, which offloads large outputs to `.rw_git/reports/` for targeted retrieval via `read_report_slice` (ADR-0001, ADR-0006).
- **Report meta-tools**: `ReportOrchestrator` runs independent analyses concurrently and returns a ranked, classified payload (ADR-0005, ADR-0017).
- **Prompts**: Reporting guidance exposed as MCP prompts and shipped as file-based agent skills (ADR-0016).

Per-tool documentation lives in [`doc/tools/`](tools/) and architecture decisions in [`doc/adr/`](adr/).

## 3. Error Handling
Following `ERROR_HANDLING.md`:
- Git execution errors are never swallowed. 
- If a `ProcessResult` yields a non-zero exit code, a strongly-typed `RwGitException` is thrown, encapsulating the underlying exit code and standard error output.
- Clients are expected to handle `RwGitException` appropriately depending on their use cases.
