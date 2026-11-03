# 0013. Ship first builds without code signing

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Signing needs paid certificates and additional pipeline work. The project owner chose to leave it out for now.

## Decision

macOS and Windows builds are unsigned. The downloads page gives illustrated instructions for bypassing the system warnings, and each release publishes SHA-256 checksums and build attestations so that downloads can be verified. The app notifies users of new versions and links to the download, and automatic self-updating waits for signing.

## Consequences

Early delivery is simpler and free. Security warnings and possible antivirus flags work against the easy-install goal, so signing should return before any wide public release.

## Alternatives considered

- **Sign from the start:** It adds cost and work before the product has been proven.
