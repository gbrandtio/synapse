# 0011. Keep all actions read-only in the first release

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Documents, tickets and web pages may contain instructions written to manipulate the AI. This is the main security risk of the design.

## Decision

Connectors and agent actions only read. Fetched content is labelled as untrusted. Fetch actions reach only hosts configured for that assistant, and hosts arriving in an imported file need the user's confirmation. The answer view never auto-loads remote content. Any future step with side effects must pass an approval step.

## Consequences

A poisoned ticket cannot make the agent change anything. Writing back, such as commenting on Jira, waits for a later release.

## Alternatives considered

- **Allow writes with a warning:** It is too risky given the audience and the threat.
