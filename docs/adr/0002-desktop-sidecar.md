# 0002. Run the engine as a local sidecar process

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

The first release is a desktop app for non-technical users, so it needs no accounts or server setup.

## Decision

Flutter starts the engine as a child process that listens only on 127.0.0.1, on a port chosen by the operating system, using a random token per launch. The token is sent over stdin. The engine exits when stdin closes. Flutter talks to it through a client generated from OpenAPI, with SSE for streaming. The bundled Ollama runs as a second private process.

## Consequences

A crash in AI or parsing code cannot kill the UI, and the same engine can later run in Docker. The cost is process lifecycle code, and a local HTTP layer between the two parts.

## Alternatives considered

- **gRPC:** It needs more tooling, and its streaming benefit is not needed.
- **`stdin`/`stdout` as the only channel:** It is harder to stream concurrently, and it would not carry over to a server deployment.
