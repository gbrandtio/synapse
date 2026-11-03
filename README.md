# Synapse

Synapse is a desktop app that lets people with little programming knowledge add documents and ask questions about them, getting answers with their sources. It runs on the user's own computer.

**Status:** early. The Apple Silicon Mac build can read a PDF and answer questions from it offline. It is not tested on Intel Macs. Windows, collections, connectors and workflows are not built yet. See [Delivery phases](docs/architecture/overview.md#delivery-phases).

## Layout

| Folder | Contents |
|---|---|
| `apps/desktop/` | The Flutter app, using Bloc |
| `engine/` | The local Python engine |
| `packaging/` | The build script, pinned models and a smoke test |
| `spikes/` | Phase 0 measurements. Not shipped |
| `docs/` | Architecture, decisions, Phase 0 results and coding guidelines |

## Develop

You need Flutter, `uv` and CMake.

```sh
cd engine && uv sync
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports

cd ../apps/desktop
flutter test --coverage && flutter analyze
```

## Build for Mac

```sh
packaging/build_llama_macos.sh <empty work folder> <llama folder>
packaging/build_macos.sh <llama folder> <fastembed cache> <model file> <gemma terms file>
```

The first script builds the llama.cpp server into the llama folder. The second script needs that folder, the embedding cache, the model file and the Gemma terms file, which must already exist. Fetching them automatically is still to do. See `packaging/models.lock.yaml`. The app needs macOS 14 or newer.

## Real data

Never commit real Jira exports or other real data. Tests use made-up data.
