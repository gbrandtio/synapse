# 0012. Fill prompt variables with a single-pass replacer

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Users write their own prompts with variables, and the values inserted can come from untrusted sources. Template engines such as Jinja or Python format strings can evaluate content, or expand variables nested inside values.

## Decision

A small single-pass replacer fills `{{variable}}` placeholders. Inserted values are never rescanned. Source text is wrapped and labelled as data automatically. A short safety instruction sits outside the user's prompt, and citations are enforced by the app. Imported files are reviewed before their first run, covering prompts, AI endpoint, sources, and hosts, because a shared file could otherwise send content to an attacker's endpoint.

## Consequences

A ticket containing `{{...}}` remains plain text, and a custom prompt cannot accidentally remove protections. Prompts have no conditionals or loops.

## Alternatives considered

- **Jinja2 sandbox:** It offers more power than users need, with more attack surface.
