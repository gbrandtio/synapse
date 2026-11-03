# FastAPI Guidelines

How the Synapse engine exposes its local API to the Flutter app. General Python rules are in [Python Guidelines](../python/index.md).

**Baseline:** FastAPI 0.162 · Pydantic 2 · Uvicorn.

## Contents

| Page | What it covers |
|------|----------------|
| [Coding Standards](./coding-standards.md) | Routes, naming, request and response models, and OpenAPI. |
| [Best Practices](./best-practices.md) | Lifespan, dependencies, security, errors, long-running jobs, SSE, and testing. |
| [Performance](./performance.md) | Avoiding event-loop blocking, serialization, streaming, and pagination. |
| [Advanced Performance](./advanced-performance.md) | Uvicorn settings, backpressure, event-loop monitoring, and startup. |

## How we use FastAPI

The API has one client today: the Flutter app on the same computer. It is still a real contract, because the Dart client is generated from its OpenAPI definition.

Routes stay thin. They validate input, call an application use case, and convert the result.

## Precedence

1. Tests and static checks enforced by CI, including the OpenAPI contract check.
2. Accepted [ADRs](../adr/README.md).
3. These guidelines.
4. Personal preference.
