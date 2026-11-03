# Python Guidelines

These pages describe how we write Python in the Synapse engine (`engine/`). They are a **shared baseline**: when a rule doesn't fit, deviate deliberately and write down why, in the PR or in an [ADR](../adr/README.md).

**Baseline:** Python 3.13, pending the Phase 0 wheel check · `uv` · Ruff · mypy in strict mode · pytest · Pydantic 2.

Framework guidance lives in its own folder: [FastAPI](../fastapi/index.md) and [LangChain and LangGraph](../langchain/index.md).

## Contents

| Page | What it covers |
|------|----------------|
| [Coding Standards](./coding-standards.md) | Naming, formatting, type hints, data types, comments, and imports. |
| [Best Practices](./best-practices.md) | Project structure, dependencies, errors, async, logging, testing, and security. |
| [Performance](./performance.md) | Measuring, everyday rules, I/O, batching, and memory. |
| [Advanced Performance](./advanced-performance.md) | Profiling, the GIL, process pools, native libraries, streaming large files, and startup time. |

## Suggested reading order

1. **New to the engine:** Coding Standards → Best Practices.
2. **Working on ingestion or a slow path:** Performance → Advanced Performance.
3. **Reviewing a PR:** jump to the *Review checklist* at the end of each page.

## Precedence

When sources disagree, follow this order:

1. Ruff, mypy and `import-linter` results enforced by CI.
2. Accepted ADRs.
3. These guidelines.
4. Personal preference.
