# 0001. Use a Python engine for all AI work

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Synapse must use LangChain and LangGraph. Their most complete versions are in Python. The UI is Flutter, so the AI work must live in a separate process. The repo also holds .NET guidelines, so .NET was a possible backend.

## Decision

The engine is written in Python, managed with `uv`, and exposes an API with FastAPI. Python 3.13 is the baseline, pending a check that all native wheels are available. .NET is not used.

## Consequences

AI features can use the libraries directly, and Python guidelines become necessary. The installer must carry a Python runtime, which adds size and packaging work.

## Alternatives considered

- **LangChain.js in a Node engine:** It has less coverage, and document and ML libraries are weaker.
- **A .NET backend calling a Python service:** It adds a second backend runtime with no benefit.
- **Python inside Flutter's process:** Flutter has no robust way to embed it, and a Python crash would take down the UI.
