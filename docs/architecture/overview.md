# Synapse architecture overview

Synapse is an MIT-licensed app that lets people with little programming knowledge add their documents, build a RAG, and create an AI agent or workflow. It also reads external sources such as GitHub and Jira, either with an API key or from just a URL or local git repo, and return structured data an agent can use.

Phase 1 code exists for the Apple Silicon Mac build. These pages describe the intended design, and each section that differs from the code says what is built. Key decisions:

| Topic | Decision |
|---|---|
| Frontend | Flutter, with Bloc for state management |
| AI framework | LangChain and LangGraph |
| First release | Desktop app, with data kept on the user's machine and no accounts |
| GitHub without a key | Public content, or a local git repo for private code. No browser login |
| Jira without a key | Public content, browser login, or an imported Excel or CSV export |
| Offline AI | The Complete download includes Ollama, a small AI model (`gemma3:1b`), and the embedding model. The re-ranking model is planned, not yet bundled |
| Workflow builder | Templates plus a simple list of steps, with a canvas possible later |
| Prompts | Users can write their own prompt in every AI step |
| RAG design | One RAG pipeline and index, with named collections per source or purpose |
| Code signing | Left out for now |
| External access | Always optional. Everything works offline on stored data |

The other pages cover [configuration](./configuration.md), the [RAG pipeline](./rag-pipeline.md), [connectors](./connectors.md), [workflows and prompts](./workflows-and-prompts.md), and [UI and UX](./ux.md). The reasons behind major decisions are in the [ADRs](../adr/README.md).

## Main idea

Three choices do most of the work of keeping Synapse easy to configure and ship.

1. **One installer contains everything.** The user downloads one file and needs no Python, Docker, git, Ollama or internet connection to start.
2. **Plain validated files describe everything.** Each collection and each assistant is a validated "blueprint" file, and every screen in the UI simply edits one. This makes sharing and upgrades straightforward.
3. **Every source returns the same record format.** GitHub, Jira, files and web pages all share one common structure, plus declared fields per source type. The RAG and the workflows never need source-specific code.

## System architecture

```
┌───────────────── Synapse desktop app (one installer) ─────────────────┐
│                                                                       │
│  Flutter UI ── HTTP + streaming (127.0.0.1, per-launch token) ──┐     │
│  (starts, watches and stops the engine)                         ▼     │
│                                                                       │
│  Python engine (bundled runtime, FastAPI)                             │
│  ├─ api/          REST and streaming endpoints                        │
│  ├─ application/  ingest, ask, query records, workflows, jobs         │
│  ├─ domain/       Blueprint, Record, Passage (no framework imports)   │
│  └─ adapters/                                                         │
│     ├─ connectors/  github, jira, files, web                          │
│     ├─ parsers/     office, pdf, optional high-quality pack           │
│     ├─ ai/          LangChain models, LangGraph workflows             │
│     ├─ stores/      SQLite, with sqlite-vec and FTS5                  │
│     └─ secrets/     OS keychain                                       │
│                                                                       │
│  Bundled models: embedding and re-ranking (run inside the engine)     │
│  Bundled Ollama and small AI model (separate local process)           │
└───────────────────────────────────────────────────────────────────────┘
                                    │ optional
                     Cloud AI, GitHub, Jira, larger local models
```

Nothing below the line is required. With the Complete download, Synapse works from its first launch with no internet connection.

Phase 1 builds only part of this diagram. The PDF reader, the SQLite search store, the question graph, the embedder and the Ollama process are built. Connectors, blueprints, the OS keychain, other parsers and workflows are not built yet.

### Technology choices

| Area | Choice | Why |
|---|---|---|
| Engine language | Python 3.13, managed with `uv` | LangChain and LangGraph are most complete in Python. The exact version is confirmed when wheel support is checked in Phase 0. |
| .NET | Not used | It has no LangChain or LangGraph and would add a second backend runtime. `docs/dotnet/` stays in place but does not apply here. |
| API | FastAPI with OpenAPI | The Dart client is generated from the API definition, so the two sides cannot silently drift apart. |
| Streaming | Server-Sent Events, using `fastapi.sse` | It covers answer text and job progress, and FastAPI has it built in since 0.135, so no extra package is needed. |
| Records and app data | SQLite | One file with no server to install or manage (see [ADR 0004](../adr/0004-sqlite-and-lancedb-for-desktop.md)). It stores records, fields, jobs, prompt history and LangGraph checkpoints. |
| Search index | `sqlite-vec` and FTS5 | They keep vectors, keywords and records in one SQLite file, so one transaction covers them all (see [ADR 0015](../adr/0015-sqlite-vec-and-fts5-as-search-store.md)). |
| Local embeddings | FastEmbed (ONNX), bundled | It runs on CPU without PyTorch, which keeps the installer small, and it does not need Ollama. |
| Local AI | Ollama and a small model, bundled in Complete | It works offline immediately. If the user already runs Ollama, Synapse can use that instead. |
| Spreadsheets | `openpyxl`, `xlrd` and Python's `csv` | They read cell values only, and never run macros or formulas. |
| Cloud AI | LangChain `init_chat_model` | OpenAI, Anthropic, Google, Azure and any OpenAI-compatible server all work through one setting. |
| Git reading | Dulwich (pure Python) | It needs no git install and never runs hooks or repo config. |
| Flutter state | `flutter_bloc`, `bloc_concurrency`, `bloc_test` | See below. |
| Flutter routes | `go_router` | It is widely used, and handles the double-click `.synapse` import links. |

### Flutter structure with Bloc

Each feature has three layers: UI widgets, then blocs, then repositories. Repositories are the only layer that calls the generated engine client, and they return `Result<T>` as `docs/flutter/CODING_STANDARDS.md` requires.

- **Bloc or Cubit:** use a `Bloc` for flows driven by events, such as chat, ingestion jobs and workflow runs. Use a `Cubit` for simple state, such as settings and theme.
- **States:** states are immutable sealed classes, so the compiler forces each screen to handle loading, success and failure.
- **Streaming:** answer text and job progress flow from SSE streams into state through `emit.forEach`.
- **Concurrency:** `bloc_concurrency` transformers set the behaviour per event. Pasting a new link cancels the previous `probe` (`restartable`), and pressing Sync twice starts one job (`droppable`).
- **Scope:** `RepositoryProvider` supplies repositories at app level. `BlocProvider` creates each bloc at the screen that owns it, and global blocs are limited to engine status and active jobs.
- **Tests:** every bloc is tested with `bloc_test` against fake repositories.

### How the app starts the engine

1. Flutter starts the engine with `runInShell: false`, as `docs/flutter/SECURITY.md` requires. The engine gets its own paths and a short list of system variables, such as `PATH` and `HOME`. Other variables, including proxy settings, are not passed.
2. Flutter sends a random access token through stdin, so it never appears in process lists.
3. The engine binds to 127.0.0.1 on port 0, so the operating system picks a free port, and reports the real port on stdout as a "ready" message.
4. If Flutter exits, stdin closes and the engine shuts itself down, so no orphan processes remain. The engine stops within about 10 seconds at most, and stops Ollama on the way out. When the app's engine object closes, the app closes stdin, waits 5 seconds, and kills the engine if it is still running.
5. Not built yet: if the engine crashes, the app does not restart it or show a banner. Background jobs are planned to be stored in SQLite and resume where they stopped. Phase 1 has no background jobs.

The PDF reader runs in a separate worker process. It has a 300 second time limit and a 512 MB file limit, so a corrupt PDF cannot take the engine down. Other parsers are not built yet.

### How the bundled Ollama runs

The engine starts `ollama serve` as a child process the first time a local AI answer needs it. It stops Ollama when the engine shuts down.

- **Private port:** `OLLAMA_HOST` points to 127.0.0.1 on a free port, so it never conflicts with a copy of Ollama the user already has, and is not reachable from other computers.
- **Private models:** `OLLAMA_MODELS` points to the models folder inside the app. The design copies the models to Synapse's data folder on first run, so they survive updates. That copy is not built yet.
- **Memory:** Synapse does not set a keep-alive time, so Ollama's default idle unload applies. A model can use several GB of memory.
- **Cloud off:** the engine sets `OLLAMA_NO_CLOUD=1`.
- **Proxies:** proxy variables are removed from Ollama's environment, and the two HTTP clients that call Ollama ignore proxy settings. Loopback traffic never uses a proxy.
- **Leftover process:** the engine saves Ollama's process ID in `ollama.pid` in the data folder. If the engine was killed, the next start stops that Ollama on macOS, after checking that the process is still Ollama. Windows does not do this yet.
- **Network use is not yet proven:** the "Nothing leaves this computer" wording in [UI and UX](./ux.md) is a goal until a full packet capture over a longer run supports it. A sampling test with `lsof`, every 0.2 seconds, saw no connection to another computer during a short run. Sampling can miss brief connections and does not see DNS, and Ollama's model-recommendations task is scheduled for hours later. See [Phase 0 results](../phase0/results.md#other-findings).
- **Licences:** Ollama and its engine, llama.cpp, are MIT. The bundled AI model must also have a licence allowing redistribution (see [Size budget for Complete](#size-budget-for-complete)), and their notices ship with the app.

## Packaging, install and deployment

| Platform | Format |
|---|---|
| macOS | `.dmg`, with separate Apple Silicon and Intel builds |
| Windows | Per-user installer, with no admin rights needed |
| Teams, later | Docker image with PostgreSQL. It must refuse to bind beyond localhost until authentication exists |

**Bundling method:** ship a prebuilt `python-build-standalone` runtime with locked dependencies inside the app, rather than a PyInstaller single file. A plain folder handles ONNX and other native libraries more predictably. No published example of this exact setup inside a Flutter app was found, so Phase 0 and Phase 1 tested it on Apple Silicon. Windows and Intel Mac are untested.

**What leaving out signing means for users.** The downloads page will include simple illustrated instructions for these warnings:

- **macOS:** the system blocks the app the first time. The user opens System Settings, Privacy & Security, and chooses "Open Anyway".
- **Windows:** SmartScreen shows a warning. The user chooses "More info", then "Run anyway".
- **Antivirus:** some products may flag unsigned apps containing Python.
- **Updates:** Synapse only notifies users of a new version and links to the download. Automatic self-updating is postponed with signing.

These warnings work against the easy-install goal, so signing should return before any wide public release.

Because users are told to bypass a warning, each release publishes SHA-256 checksums and GitHub build attestations, and the instructions link only to the official releases page and explain how to check a download.

### Two downloads, built from the same pipeline

| Download | Contains | Best for |
|---|---|---|
| **Synapse Complete** (default) | App, engine, Ollama, small AI model, and embedding model. The re-ranking model is added when re-ranking is built | Everyone, and especially offline use |
| **Synapse Standard** | App, engine, embedding model, and re-ranking model once built | Cloud AI users, people with their own Ollama, and updates |

The embedding model is in both, so search always works offline. With Standard, local models download inside the app when needed.

### GitHub limits and how they apply

| GitHub limit | Value | What Synapse does |
|---|---|---|
| Release asset size | Each file under 2 GiB | Every installer must be under this. CI fails a build above 1.9 GiB |
| Assets per release | Up to 1,000 | Far more than we need |
| Total release size and bandwidth | No limit | Downloads are free to host |
| Files in the git repository | Warning above 50 MiB | Models are never committed |
| Git LFS | Limited by a storage and bandwidth quota | Not used |
| Single push | 2 GiB | Not relevant, as models stay out of git |

Models live only in release assets. `packaging/models.lock.yaml` records each model's source, licence and SHA-256 hash. CI downloads the models, verifies the hashes and builds the installers, so a build is repeatable and cannot silently pick up a different model.

GitHub's docs pages for some of these limits are old, so Phase 0 confirms them with a real upload of a file close to 2 GiB. It also checks that CI runners have the disk space for these builds.

### Size budget for Complete

Measured on 2026-11-03 for the Apple Silicon build.

| Part | Size | Basis |
|---|---|---|
| Complete `.dmg`, whole app | 1,128,102,926 bytes (1,075 MB) | Measured. Built by `packaging/build_macos.sh`, against the 1.9 GiB limit |
| Models folder: AI model and embedding model | 897 MB installed | Measured |
| Ollama | 101 MB installed | Measured, trimmed |
| Python runtime | 74 MB installed | Measured |
| Python packages | 225 MB installed | Measured |
| Windows | Unknown | Not measured. One third-party figure puts Ollama on Windows at 745 MB |

The installed parts add up to more than the `.dmg`, because the `.dmg` is compressed. The Apple Silicon build has about 0.9 GB of room under the limit. The re-ranking model is not in the build, because re-ranking is not built yet.

**The honest consequence:** this rules out the popular 8 GB laptop models. Reported sizes are about 1.7 GB for Gemma 3 2B, 2 GB for Llama 3.2 3B, and 2.5 GB for Phi-4 Mini. Only a very small model fits. Complete bundles `gemma3:1b`, which has no tool calling. Such a model is suitable for answering from retrieved passages, but it will be weaker at complex reasoning and agent work.

**Model rules:**

- **Licence:** Apache or MIT, or another licence that clearly allows redistribution.
- **Language:** good English quality. English is the only supported language.
- **Features:** reliable structured output, for field filters and Extract data steps.
- **Hardware:** runs acceptably on CPU with 8 GB of memory.

Phase 0 tested candidates against these rules. The table above shows measured sizes. See [Phase 0 results](../phase0/results.md#size).

**One file is a firm decision.** Complete stays a single download, even though a two-file version could carry a better 2 to 3 GB model. Synapse ships the best model that fits, and people who want better answers can add a larger model or a cloud AI after installing. A larger model can be downloaded inside the app. See [ADR 0010](../adr/0010-bundled-models-and-github-limits.md).

### Other packs and upgrades

These optional packs download only when needed:

| Pack | Downloaded when | Why it is optional |
|---|---|---|
| Larger local AI models | The user chooses one, and the computer has enough memory | Better answers, but too large to bundle |
| High-quality documents (Docling) | A scanned PDF or complex tables are detected | Reported at about 1 GB or more |
| Browser login for Jira (Playwright) | The user first needs private Jira access without a key | Only some users need it |

**Upgrades:** the UI and engine always ship together, so version mismatches cannot occur. Blueprints carry a schema version and migrate automatically. The design has Complete copy Ollama and its models to the data folder on first run, so they survive updates. This copy is not built yet. The update notice therefore links to the smaller Standard download, and existing users do not download 2 GiB again.

**Release pipeline:** GitHub Actions builds both downloads on Windows and macOS, because Python native libraries cannot be cross-compiled reliably. Each build is installed and smoke-tested with the network off, by adding a sample document and asking a question using the bundled model. Releases go to GitHub Releases. Phase 1 has no CI yet, so the Mac build is made by hand with `packaging/build_macos.sh`.

**Licence gate:** CI fails on AGPL or GPL-only dependencies. This matters because PyMuPDF and PyMuPDF4LLM are AGPL or commercially licensed, which conflicts with shipping Synapse as MIT, so Synapse does not use them despite their good reviews.

**Privacy:** no telemetry unless the user opts in. LangSmith tracing is off in releases, and is used only in development with test data.

## Repository layout

```
synapse/
├─ apps/desktop/          Flutter app, organised by feature
├─ engine/                Python project (uv), src/synapse_engine/...
├─ contracts/             OpenAPI, blueprint, record and field schemas
├─ packaging/             Installer scripts and models.lock.yaml (no model files)
├─ templates/             Starter blueprints
├─ .github/workflows/     CI and release builds
└─ docs/
   ├─ architecture/  adr/  python/  langchain/  fastapi/  bloc/  dotnet/  flutter/
```

The engine follows the modular-monolith and Clean Architecture guidance in `docs/dotnet/architecture-principles.md`, which applies regardless of language. `import-linter` enforces in CI that `domain/` never imports frameworks.

The existing `docs/flutter/` rules apply to the UI, including `Result<T>`, no `dynamic`, Isolates for heavy work, and 100% coverage, with generated code excluded. Those files are written about the `rw_git` package, so its specific names do not carry over. Read `rw_git` in those pages as "the Synapse app" when applying their general rules.

## Delivery phases

| Phase | Output | Done when |
|---|---|---|
| **0. Tests** | Answers to the risks below | Each has a written result and an ADR |
| **1. Walking skeleton** | Complete and Standard installers: drop a PDF, ask a question, get a cited answer | Complete works on a clean machine with the network off, on Windows and macOS, and is under 2 GiB |
| **2. Real RAG** | Collections, the full pipeline, sync, settings with descriptions, test screen | Meets recall targets set from the Phase 0 baseline |
| **3. Connectors** | GitHub and Jira with keys and public access, local git repos, Excel and CSV import, field capture, and Query records | Same record schema passes contract tests for each, and comments and start dates work end to end from both Jira and a spreadsheet |
| **4. Browser login** | Optional pack and session flows | Private Jira works through SSO on a test site |
| **5. Workflows** | Step builder, custom prompts, prompt library, Agent step, templates, schedules, approvals | All five templates run end to end, and each can be rewritten with a custom prompt |
| **6. Polish and launch** | `.synapse` sharing, accessibility, install instructions | Non-technical testers succeed unaided |
| **Later** | Signing and auto-update, canvas, team mode with PostgreSQL, write actions, MCP, contextual retrieval, graph-based search | |

**Phase 1 status.** Phase 1 is partly done. Only the Apple Silicon Mac build exists. There is no Windows build, no CI, and no tested Intel Mac build. Models are fetched by hand and passed to the build script. Phase 1 is not complete until Complete also works on Windows.

**Phase 0 tests.** Research could not settle these, so they need real tests. [Phase 0 results](../phase0/results.md) records what has been answered:

1. Does the bundled runtime work inside a Flutter app on Windows and macOS, and how large is the installer? It works on Apple Silicon, and its size is measured. Windows and Intel Mac are untested.
2. How well do small English embedding and re-ranking models perform through FastEmbed? This decides the default model, and the available re-rankers are not yet confirmed.
3. Can one embedding model serve prose, code and tickets together? This tests the one-index decision. Does the pipeline clearly beat naive RAG on sample sets of each?
4. Does LanceDB hold up at about 100,000 passages on an ordinary laptop, with filter columns for many fields? How does SQLite plus `sqlite-vec` compare? Answered in [ADR 0015](../adr/0015-sqlite-vec-and-fts5-as-search-store.md).
5. Is Dulwich fast enough on a large repository?
6. Does the Jira browser session work headlessly after login, or must the window remain visible? What is the real download size of Playwright?
7. Is the combination of `pypdfium2` and MarkItDown good enough by default, and how large is `docling-slim`?
8. Do Tree-sitter's language packages fit the installer budget? Which common Ollama models reliably support structured output and tools?
9. **Bundled model:** does any model that fits the budget meet the model rules in [Size budget for Complete](#size-budget-for-complete), with acceptable answers and speed on an 8 GB computer? This picks the bundled model. Complete stays one file either way, so if no candidate is acceptable, the question goes back to the project owner.
10. **Bundled Ollama:** what is its real size per operating system, how much do GPU libraries add, and can unneeded ones be removed safely? Does a private `OLLAMA_MODELS` folder work when pre-filled by an installer, on Windows and macOS? Can Ollama run from the data folder after being copied there, including on unsigned macOS builds? If not, Complete users must update with Complete.
11. **GitHub limits:** does a build close to 2 GiB upload and download reliably, and do GitHub Actions runners have the disk space? Do Windows and macOS installers handle a payload of this size?
12. **Jira exports:** done, using the only export available, a Jira Cloud `.csv`. [What a real export looks like](./connectors.md#what-a-real-export-looks-like) records the results. No other samples will be collected, so tests build made-up files in that format, including filled-in start dates.

**Main risks**

| Risk | Response |
|---|---|
| The bundled model gives mediocre answers, and users judge Synapse by that first impression | Test candidates in Phase 0, ship the best that fits, and offer larger models or cloud AI on the first screen |
| Local AI is slow on weak computers | Check memory first, and recommend cloud AI honestly when local would be poor |
| Complete exceeds 2 GiB as parts grow | CI fails above 1.9 GiB. The response is to remove unneeded GPU libraries or choose a smaller model, because Complete stays one file |
| Other exports may differ from the one sample, such as `.xlsx`, `.xls` or Data Center | A mapping screen the user can correct, a file preview that lists problems before importing, and tests with made-up data in the sample's format. Differences are fixed when a user reports them |
| Security warnings put off non-technical users, since builds are unsigned | Clear illustrated install instructions, and signing returns before wide release |
| Jira browser login breaks or is blocked by company policy | Token and spreadsheet import remain available, failures are clearly explained, and stored data keeps working |
| One embedding model handles code poorly | Phase 0 measures this. If so, a code-specific index can be added without changing what users see |

## Verification of code phases

- **Engine:** `pytest`, Ruff, strict type checks, and `import-linter`.
- **Flutter:** `dart format --line-length=80 .`, `dart analyze`, `flutter test --coverage`, and `bloc_test` for every bloc.
- **Connectors:** contract tests against recorded responses, covering each access method, and confirming that custom fields and comments map correctly.
- **Local repos:** tests confirm no hook or repo config runs, the repo is unchanged afterwards, and private-repo errors offer the local copy option.
- **Spreadsheets:** exports produce the same records as the API for the same tickets. Real exports contain people's names and company data, so they are never committed, and committed test files use made-up data in the same format. Tests cover ambiguous dates, missing keys, repeated comment columns, malformed files, HTML disguised as `.xls`, and macros, which must never run.
- **Packaging:** CI verifies every model's hash and licence entry, fails above 1.9 GiB, and confirms no model files are in git.
- **Quality:** the RAG test set for each source type runs in CI against the naive baseline.
- **Settings:** a test fails if any blueprint setting lacks a description, so the UI can never show an unexplained option.
- **Prompts:** tests confirm that `{{...}}` inside source text stays as plain text, and that unknown variables are rejected before running.
- **Offline:** Complete is installed and first launched with the network off. It can ingest files, answer questions, and run a workflow using only bundled models. A workflow whose source is unreachable follows its Fetch setting.
- **Security:** a poisoned-document test, run with both default and custom prompts, confirms an injected instruction cannot trigger an action or a leak.
- **End to end:** install on a clean machine, create collections from documents, a local git repo and a Jira Excel export, ask one assistant using all three, and get cited answers. Ask for tickets by start date, and get a count with its date. Then edit a step's prompt, restart mid-sync, and confirm the job resumes.

## Sources

- Packaging: [flutter_python_starter](https://github.com/MobilePython/flutter_python_starter), [shipping Python to end users](https://pydevtools.com/handbook/explanation/how-do-i-ship-a-python-application-to-end-users.md)
- GitHub: [release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), [large files](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github), [Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage), [push limit](https://docs.github.com/en/get-started/using-git/troubleshooting-the-2-gb-push-limit)
- Ollama and models: [Ollama installation](https://mintlify.com/ollama/ollama/installation), [Windows download size](https://lilys.ai/notes/zh/bitcoin-bear-market-20251214/ollama-windows-install-ai), [small model sizes](https://www.promptquorum.com/de/local-llms/best-beginner-local-llm-models)
- Search index: [self-hosted vector database comparison](https://d-central.tech/self-hosted-vector-databases/), [LanceDB hybrid search](https://docs.lancedb.com/search/hybrid-search)
- FastAPI: [Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/)

**Not yet confirmed against official sources:** PyMuPDF's licence terms, the macOS and Windows unsigned-app warnings, Ollama's MIT licence, and candidate model sizes and licences. Phase 0 and the licence gate check these.
