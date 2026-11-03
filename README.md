# Synapse

Synapse is a desktop app that lets people with little programming knowledge add documents and ask questions about them, getting answers with their sources. It runs on the user's own computer.

**Status:** early. The Apple Silicon Mac build can read a PDF and answer questions from it offline. It is not tested on Intel Macs. Windows, collections, connectors and workflows are not built yet. See [Delivery phases](docs/architecture/overview.md#delivery-phases).

**Do not share the app yet.** Synapse's own terms are a draft in `apps/desktop/assets/legal/TERMS.txt`. They have placeholders and have not had legal review.

## Layout

| Folder | Contents |
|---|---|
| `apps/desktop/` | The Flutter app, using Bloc |
| `engine/` | The local Python engine |
| `packaging/` | Build scripts, the pinned model list, a model fetch script and a smoke test |
| `.github/workflows/` | CI and the Mac build. Neither has run yet, because nothing is pushed |
| `spikes/` | Phase 0 measurements. Not shipped |
| `docs/` | Architecture, decisions, Phase 0 results and coding guidelines |

## Develop

You need Flutter and `uv`.

```sh
cd engine && uv sync
uv run pytest && uv run ruff check . && uv run mypy && uv run lint-imports

cd ../apps/desktop
flutter test --coverage && flutter analyze
```

The CI workflow in `.github/workflows/ci.yml` runs these checks. It also checks Dart formatting, and it requires 100% Flutter line coverage. It has never run.

## Build for Mac

You need Xcode and `uv`. The llama.cpp server also needs CMake and Git.

```sh
packaging/build_llama_macos.sh <empty work folder> <llama folder>
packaging/build_macos.sh <llama folder> <models folder>
```

The first script builds the llama.cpp server into the llama folder. The second script downloads the models into the models folder if they are not there. It checks each file against `packaging/models.lock.yaml`, and a wrong hash stops the build. The first run needs the internet and about 900 MB of space for the models. The result is `apps/desktop/build/Synapse-Complete-macos-arm64.dmg`, about 1 GB. The app bundle is `Synapse.app`, and it needs macOS 14 or newer.

### Smoke test

The smoke test runs the built engine as the app does. It asks three questions and reports any connection to another computer. It needs the internet on, because it checks what the engine tries to reach. Make a test PDF first, using an absolute path:

```sh
cd engine && uv run python ../packaging/make_test_pdf.py <pdf file>
python3 packaging/smoke_test.py <engine folder> <pdf file> <empty data folder> [idle seconds]
```

The engine folder is `apps/desktop/build/macos/Build/Products/Release/Synapse.app/Contents/Resources/engine`. The idle seconds are optional, and the default is 20. The script fails if anything tries to leave the computer.

The app test runs the real app against the built engine:

```sh
cd apps/desktop
SYNAPSE_RESOURCES=<engine folder> SYNAPSE_TEST_PDF=<pdf file> flutter test integration_test/app_test.dart -d macos
```

## Real data

Never commit real Jira exports or other real data. Tests use made-up data.
