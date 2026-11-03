# 0008. Define access methods per source

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Users may have no API key. Browser sessions cannot reliably provide GitHub data, because GitHub web sessions do not authorise its API. Local git repos already hold private code without any credentials.

## Decision

GitHub: a token, either pasted or obtained through the OAuth device flow, then anonymous API for public repos, then a local git repo read with Dulwich. Issues and pull requests are unavailable from a local repo, and the UI says so. Jira: token, then anonymous API, then browser login calling Jira's REST API from inside the page, or an imported spreadsheet. Browser access is read-only, uses a dedicated profile, and never bypasses security challenges.

## Consequences

No fragile scraping of GitHub is needed. Private GitHub issues do require a token. Jira browser login can be blocked by company policy, so token and spreadsheet routes remain.

## Alternatives considered

- **Browser login for GitHub:** It depends on scraping pages that can change.
- **Public access only for Jira:** It would exclude private projects for users without a key.
