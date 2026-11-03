# 0019. Keep telemetry libraries out of the bundle

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Synapse promises that nothing leaves the computer. A test that logged every DNS lookup found that the engine contacted `mobile.events.data.microsoft.com`, and a connection to Microsoft was established.

The cause was onnxruntime, which runs the embedding model. From version 1.29 its Mac builds turn telemetry on by default, and it starts about 9 seconds after the library is imported. No newer limit was set, so the build had picked up 1.31.1. It also wrote a device ID and a small database under `~/Library/Application Support/Microsoft/DeveloperTools/.onnxruntime`.

The one event captured held the device model, chip, memory, macOS version, process name, library version and a hashed device ID. Its source code also defines events with the model file name, timings and cleaned error messages. We found no way for document text or questions to be sent, but that comes from reading the source. We could not capture every event type.

Earlier checks missed this. Blocking the internet hides telemetry that only runs online, and sampling connections can miss a short one.

## Decision

- **Pin onnxruntime to 1.28.0,** the newest version without this code. Removing the code is stronger than switching it off.
- **Set `ORT_DISABLE_TELEMETRY=1`** when the app starts the engine, in case a later version needs it.
- **Fail the build** if any bundled library contains Microsoft's telemetry address.
- **Fail the smoke test** if any lookup or connection leaves the computer. It runs with the internet on, and logs calls through `packaging/netlog.c`.

## Consequences

onnxruntime cannot be updated by accident. Moving past 1.28.0 needs a decision, and a build of it without telemetry, or proof that the off switch holds.

The logger sees lookups by name and direct connections. It does not see connections made inside Apple's network library to an address that needs no lookup. A long packet capture is still the stronger proof, and it needs administrator rights.

Each new dependency can bring the same problem, so the smoke test must run on every release.

## Alternatives considered

- **Off switch only:** it works when set before the import. It is too late if set afterwards, and calling `disable_telemetry_events()` after import still contacted Microsoft.
- **Build onnxruntime ourselves without telemetry:** this allows newer versions, but it is much more build work than we need now.
