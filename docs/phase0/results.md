# Phase 0 results

Measured on 2026-11-03 on one Apple M4 Mac with 24 GB of memory. The scripts and raw figures are in `spikes/`.

**How far to trust these:** the search test set is small and partly hand-written, with 410 passages. The docs and tickets sets have 12 and 18 questions, so one question moves a score by 8 or 6 points. Speeds are upper bounds, because this Mac is faster than an ordinary laptop. Nothing here was run on Windows or on an Intel Mac.

## Summary

| # | Test | Result | Status |
|---|---|---|---|
| 1 | Bundled runtime inside a Flutter app | Works on Apple Silicon. Verified by the integration test `apps/desktop/integration_test/app_test.dart` and by `packaging/smoke_test.py`. Both ran with internet blocked through `sandbox-exec`, and with uv's Python folder hidden. Windows and Intel Mac are untested | Partly answered |
| 2 | Small English models | `bge-small-en-v1.5` (67 MB) was the best small model | Answered for now |
| 3 | One model for prose, code and tickets | Yes on this test set. A heavily weighted pipeline did not beat vector search | Answered for now, retest in Phase 2 |
| 4 | Search store | sqlite-vec with FTS5 is fast enough to 300,000 passages. See [ADR 0015](../adr/0015-sqlite-vec-and-fts5-as-search-store.md) | Answered, accepted |
| 5 | Dulwich on a large repository | Fast enough | Answered |
| 6 | Jira browser session | Playwright's Python package is 146 MB. Headless behaviour needs a real SSO site | Open |
| 7 | PDF reading | `pypdfium2` read English, Greek, a table and two columns correctly on one test file. It does not mark headings | Partly answered |
| 8 | Tree-sitter and tool support | 22 languages add about 50 MB, and must be bundled. Four of five small models support tools | Answered |
| 9 | Bundled model | `gemma3:1b` scored best. See [ADR 0017](../adr/0017-bundled-ai-model.md) | Answered, accepted |
| 10 | Bundled Ollama | On Mac it shrinks from 501 MB to 101 MB and still works, including from a pre-filled model folder. Windows is untested | Partly answered |
| 11 | GitHub limits near 2 GiB | Not tested. This needs CI and a real upload | Open |
| 12 | Jira exports | See [What a real export looks like](../architecture/connectors.md#what-a-real-export-looks-like) | Answered |

## Search quality

Each figure is how often the right passage reached the top 6. All content shares one index.

**Embedding models, vector search only:**

| Model | Size | Code by meaning (266) | Docs (12) | Tickets (18) | Passages per second |
|---|---|---|---|---|---|
| `bge-base-en-v1.5` | 210 MB | 93% | 92% | 100% | 7 |
| **`bge-small-en-v1.5`** | 67 MB | 91% | 83% | 100% | 21 |
| `nomic-embed-text-v1.5-Q` | 130 MB | 84% | 83% | 100% | 11 |
| `all-MiniLM-L6-v2` | 90 MB | 82% | 83% | 100% | 114 |
| `jina-embeddings-v2-small-en` | 120 MB | 75% | 92% | 100% | 52 |
| `snowflake-arctic-embed-xs` | 90 MB | 40% | 67% | 94% | 55 |

`nomic` may need query and document prefixes that were not confirmed, so its score may be low.

**Methods, with `bge-small-en-v1.5`:**

| Method | Code by meaning (266) | Docs (12) | Tickets (18) | Exact terms in code (46) | Exact terms in tickets (10) |
|---|---|---|---|---|---|
| Vector only | 91% | 83% | 100% | 100% | 90% |
| Keyword only | 61% | 67% | 89% | 100% | 100% |
| Hybrid, equal weights | 77% | 83% | 94% | 100% | 100% |
| Hybrid, keyword weight 0.1 | 90% | 83% | 100% | 100% | 90% |
| **Hybrid, 0.1 or 1.0 for exact-looking questions** | 90% | 83% | 100% | 100% | 100% |
| Hybrid 0.25, re-rank top 12 | 82% | 92% | 100% | 100% | 100% |

Findings:

- **Equal weighting hurts.** It lowered code from 91% to 77%, so the planned "balanced" default is replaced by [ADR 0016](../adr/0016-search-defaults.md).
- **The adaptive rule was tuned on these same questions,** so Phase 2 must test it on new ones.
- **Re-ranking did not clearly help,** and it costs about 0.6 to 1 second per question for 40 candidates. Twelve candidates should cost about a third of that, by proportion rather than by measurement.
- **A small index flatters vector search.** Exact code names scored 100% with vector search alone, which may not hold in a large index. Phase 2 must retest at realistic size.

## Search store

| Passages | Vector | With field filter | Hybrid with filter | Disk |
|---|---|---|---|---|
| 10,000 | 4 ms | 3 ms | Not re-measured | 26 MB |
| 100,000 | 39 ms | 34 ms | 35 to 48 ms | 256 MB |
| 300,000 | 120 ms | 108 ms | 105 to 148 ms | 768 MB |

These use 384-dimension vectors and made-up text, on one thread per query. 768 dimensions roughly double the vector time. The 1,000,000-passage run was stopped before it finished.

LanceDB at 100,000 passages took 6 ms for vector search and 178 MB on disk. On random vectors, which are a worst case, its default index found 17% of the true top 10 results.

**sqlite-vec behaviour confirmed:** rollback covers vectors and records together, delete and update work, a killed writer leaves the file intact with no partial rows, and readers are not blocked by a writer. It allows 16 metadata columns and `k` up to 4,096, so filters use ordinary tables.

**A query trap:** `rowid IN (subquery)` on an FTS5 table took 1.6 seconds at 100,000 passages and 11 seconds at 300,000. A join takes 1 to 12 ms at 100,000. A test must keep this form out.

## Bundled AI model

GPU off and four threads. Scoring uses fixed keyword checks, so small differences are ties.

**Later update (2026-11-03):** the table below was measured on Ollama. Ollama's network use was hard to verify, and it ran as two processes. These reasons led to [ADR 0018](../adr/0018-llama-cpp-instead-of-ollama.md), which bundles the llama.cpp server instead. The same Gemma model was rerun on llama.cpp with `spikes/bench_llama.py`. It scored 12 of 12 on answers, 5 of 5 on extraction, and 3 of 4 on filters. The one filter miss was "List finished tickets", which invented an assignee named "admin". On Ollama the same test scored 11, 5 and 4. These are small keyword-scored sets, so treat the two results as a tie.

| Model | Download | Licence | Answers (12) | Extraction (5) | Filters (4) | Tools | Tokens per second | Memory |
|---|---|---|---|---|---|---|---|---|
| **`gemma3:1b`** | 769 MB | Gemma terms | 11 | 5 | 4 | No | 85 | 1.0 GB |
| `qwen2.5:1.5b` | 940 MB | Apache 2.0 | 10 | 5 | 2 | Yes | 75 | 1.4 GB |
| `granite4:350m` | 676 MB | Apache 2.0 | 10 | 4 | 3 | Yes | 23 | 1.0 GB |
| `qwen3:0.6b` | 498 MB | Apache 2.0 | 8 | 3 | 3 | Yes | 134 | 1.1 GB |
| `qwen2.5:0.5b` | 379 MB | Apache 2.0 | 7 | 3 | 1 | Yes | 163 | 0.7 GB |

`qwen3:0.6b` obeyed a prompt-injection attempt and is ruled out. Several failures in the others were answers that gave only a citation, such as `[2]`, which a stronger prompt may fix.

**Sources are enforced by the app, not by the prompt.** Citations that point to no passage are dropped. If the AI cites nothing, the best passage is shown as a "Likely source". An answer that says it could not find the answer has no sources. This is built in Phase 1, in `engine/src/synapse_engine/adapters/ai/ask_graph.py`.

## Size

Measured on 2026-11-03 for the Apple Silicon build. The Ollama rows were replaced by the llama.cpp server in [ADR 0018](../adr/0018-llama-cpp-instead-of-ollama.md), so these figures are historical:

| Part | Size | Basis |
|---|---|---|
| Complete `.dmg` | 1,128,102,926 bytes (1,075 MB) | Built by `packaging/build_macos.sh`, against the 1.9 GiB limit |
| Models folder: AI model and embedding model | 897 MB installed | Measured |
| Ollama, trimmed | 101 MB installed | Measured |
| Python runtime | 74 MB installed | Measured |
| Python packages | 225 MB installed | Measured |

The installed parts add up to more than the `.dmg`, because the `.dmg` is compressed. The Apple Silicon build is about 0.9 GB under the 1.9 GiB limit. The build has the embedding model only, because re-ranking is not built yet.

Windows sizes are unknown. One third-party figure puts Ollama on Windows at 745 MB, so the Windows build may be much larger.

## Other findings

- **Dulwich** on Flutter's repository (15,665 files, 89,110 commits, 574 MB pack): listed files in 0.6 s, read 5,000 files in 0.8 s, and walked 500 commits in 0.4 s. The repository was unchanged afterwards.
- **Tree-sitter:** `tree-sitter-language-pack` downloads parsers on first use, which breaks offline use. CI must fetch them at build time and the app must load only bundled copies.
- **Docling:** `docling-slim` installs at 131 MB, but this excludes its models, so its real size is still unknown.
- **MarkItDown** needs its own PDF extra to read PDFs. It is not needed, because `pypdfium2` reads them.
- **Later update (2026-11-03):** the checks below also missed real telemetry from onnxruntime in the Python engine, because they blocked the internet or only sampled connections. See [ADR 0019](../adr/0019-no-telemetry-in-the-bundle.md).
- **Ollama network use is unresolved.** Its log shows cloud features on by default and a scheduled model-recommendations task. The engine sets `OLLAMA_NO_CLOUD=1`, but the recommendations task is still scheduled. In a short run, `lsof` sampling every 0.2 seconds (in `packaging/smoke_test.py`) saw no connection to another computer, and the app works with internet blocked. This does not settle the question. Sampling can miss brief connections and does not see DNS, and the recommendations task is scheduled for hours later. Keep this unresolved until a full packet capture over a longer run shows no connection to another computer. Only then can "Nothing leaves this computer" be stated.
