# RAG pipeline

There is one pipeline for everything. It adapts automatically to each source type, so users do not choose a RAG method.

## Collections: one index, many purposes

A **collection** is a named group of sources, such as "GitHub code", "Product manuals" or "Support tickets". Every passage in the shared index carries its collection ID, and searches filter by that ID *before* ranking, so that results come only from the allowed collections.

Reasons for this choice:

- **Simplicity:** there is one index to build, test and repair, and one set of defaults to tune.
- **Better cross-source results:** all scores come from one index, so results compare fairly.
- **Flexibility:** assistants mix collections freely, and a source can be moved without re-embedding.

Separate indexes would make sense only if different sources proved to need different embedding models, which Phase 0 tests. The design leaves this possible later.

## What adapts to each source type

Users do not configure this, because Synapse knows the source type.

| Source type | How content is split | Search adjustments |
|---|---|---|
| Documents and web pages | By headings, keeping the section path | Adds the surrounding section |
| Code | By function and class with Tree-sitter, falling back to size for unsupported languages | Favours exact matches. Names like `getUserById` also match `user` |
| Tickets (Jira, GitHub issues, PRs) | A summary passage, plus one passage per comment linked to the ticket | Filters on fields, and favours recent items |
| Commits | One passage per commit message | Favours recent items |

## RAG methods evaluated

These are the main methods, in plain terms, and what Synapse does with each. Index cost is paid once per document, and question cost is paid on every question.

| Method | How it works | Good at | Weak at | Index cost | Question cost | Decision |
|---|---|---|---|---|---|---|
| **Naive RAG** | Split text, embed it, take the closest passages, and send them to the AI | Small, clean content; speed | Exact terms and names; passages that lose meaning when cut | Low | Low | **Test baseline only:** it is the standard to beat |
| **Hybrid search** | Combines meaning-based and exact keyword search | Product names, error codes, identifiers | Needs a merging step | Low | Low | **Included** |
| **Re-ranking** | A second, more careful local model reorders the results | Precision, by removing near-misses | Adds some delay per question | None | Low to medium | **Included, off by default:** Phase 0 found no clear gain ([ADR 0016](../adr/0016-search-defaults.md)) |
| **Parent-document (small-to-big)** | Searches small passages, but gives the AI the surrounding section | Answers needing context | Uses more of the token budget | Low | Low | **Included** |
| **Corrective RAG (CRAG)** | Checks whether results are good enough, and retries or declines if not | Honest answers on incomplete content | One extra AI call when retrying | None | Medium | **Included, in a light form:** one retry, then "I couldn't find this" |
| **Self-querying** | The AI turns a question into filters on fields | Tickets and other structured data | Content with no useful fields, or models without structured output | None | Low to medium | **Included where fields exist**, falling back to plain search |
| **Contextual retrieval** | The AI writes a sentence of context for each passage before indexing | Long reports where passages rely on earlier text | Slow and costly to index, especially on local AI | High | Low | **Later:** add as one setting if tests show a clear gain |
| **Agentic RAG** | An AI agent decides what to search, and may search again | Multi-part questions | The slowest and most expensive option, less predictable, and needs a model that supports tools | None | High | **Workflow step, not a RAG type** |
| **Multi-query / RAG-Fusion** | Rewrites a question several ways and merges the results | Vague questions | Extra AI call; can drift off topic | None | Medium | **Not in first release** |
| **HyDE** | The AI writes a fake answer, and searches with that | Questions worded unlike the source | Misleads search when the guess is wrong; poor on exact terms | None | Medium | **Not in first release** |
| **Self-RAG** | A specially trained model decides when to search and critiques itself | Research settings | Needs specially trained models | Medium | High | **Not adopted:** the Corrective approach meets the practical need |
| **RAPTOR** | Builds a tree of summaries over clusters of passages | "What is this whole report about?" questions | Costly to build and to keep updated | High | Low | **Later**, if tests show the need |
| **GraphRAG** | Builds a graph of entities and relationships | Questions about connections across documents | Very costly with AI extraction, and hard to explain | Very high | Medium to high | **Later**, starting with graphs built without AI from code structure and ticket links |

The published evidence supports this choice. Anthropic reported that top-20 retrieval failures fell from 5.7% to 3.7% with contextual embeddings, to 2.9% with keyword search added, and to 1.9% with re-ranking added. This is one vendor's test of one retrieval metric, so Phase 0 repeats a comparison on our own test sets. A 2026 paper also found that graphs built from code structure gave more reliable results than AI-extracted ones, at about one-twentieth of the indexing cost. Several sources recommend hybrid search and re-ranking as the default, and adding complexity only when tests show a need.

## Adding knowledge

| # | Stage | What happens |
|---|---|---|
| 1 | Collect | Files, folders, URLs and connectors produce records. A SHA-256 hash skips unchanged content, so re-syncing is cheap. |
| 2 | Read | Office files and HTML go through MarkItDown, and PDFs go through `pypdfium2`. Spreadsheets recognised as tickets or tables use the [spreadsheet importer](./connectors.md#importing-excel-and-csv-files) instead. Pages with no text layer trigger the offer to download the high-quality pack. Page numbers and headings are kept. |
| 3 | Clean | Removes repeated headers and footers and empty pages, and normalises text. |
| 4 | Protect | Skips files such as `.env` and private keys, and redacts obvious secrets before anything is embedded. This is on by default, through the *Remove secrets from content* setting. |
| 5 | Store record | The full record and its fields go into SQLite. |
| 6 | Split | Follows the source type's rules, then splits by size. Each passage keeps its location, such as "Manual > Install > Windows". |
| 7 | Embed | Runs in batches and caches by content hash and model. |
| 8 | Index | Stores passages in SQLite, using `sqlite-vec` for vectors and FTS5 for keywords. Field filters use ordinary tables. |
| 9 | Publish | New content goes live only when a batch completes, so a failed sync never breaks a working assistant. |

**Phase 1 status:** only PDFs are read. Passages are split by word count, with overlap, so heading paths are not kept yet. Unchanged files are skipped by hash. The cleaning, secret removal and record steps are not built yet, and neither are the other source types.

The user sees plain progress such as "Reading 42 of 120 files". A results list shows anything skipped and why.

## Answering a question

This is a LangGraph graph with bounded loops, so it always finishes.

```
question
  → rewrite as a standalone question (only if there is chat history)
  → turn details into field filters, where fields exist
  → hybrid search (vector + keyword, merged with weighted Reciprocal Rank Fusion)
  → re-rank with a local model (optional, off by default)
  → good enough? ── no ──→ reword once and search again
       │                        │ still weak
       ▼ yes                    ▼
  → build context           say "I couldn't find this in your documents"
    (remove duplicates, add surrounding section and the record's fields,
     fit the token budget)
  → generate a streamed answer with numbered citations
  → check that each citation points to a real passage
```

Saying "I couldn't find this" is deliberate, because a wrong answer costs a non-technical user more than no answer. Citations open the source at the right page, ticket or file.

**Phase 1 status:** the graph is smaller. It runs search, a check against a similarity threshold, a streamed answer, and the citation check. The question rewrite, field filters, re-ranking, the retry and the surrounding-section step are not built yet. No re-ranking model is bundled.

**Escaping.** Each passage is wrapped in a `<passage>` tag that holds its number, document name and page. The passage text and the document name are escaped first. Angle brackets become entities and double quotes become single quotes, so text in a file cannot form a tag or break out of its passage. The system prompt tells the model to ignore instructions inside passages.

**Exact terms.** A short question with an exact-looking term, such as an error code, is answered when keyword search gives a top match. This happens even if the meaning score is below the threshold.

**Likely sources.** If the AI cites no passage, the best passage is added and marked as a "Likely source". The engine enforces this, not the prompt, so a prompt cannot remove the source. An answer that declines has no sources.

## Counting and listing questions

Search returns a sample of passages, so it cannot reliably answer "how many tickets are open?". Those questions are answered from the stored records instead:

1. The AI converts the question into validated filters on stored fields, such as `status = Open`.
2. SQLite runs the query, so the number is exact for the stored data, and is not an AI estimate.
3. The answer states its date, for example "12 open tickets, as of the last sync today at 09:00".

This needs no connection to Jira. If a model cannot produce structured output, the app explains that this type of question needs a different model, or the user can use the Query records step, which has a plain form.

## Measuring quality

- **For users:** a "Test my assistant" screen where they enter sample questions, or generate them from their documents. It reports results such as "Found the right source for 9 of 10 questions", and suggests a fix when results are poor.
- **For developers:** a fixed test set for each source type runs in CI, measuring recall@k and citation correctness against the naive baseline, so a dependency or settings change cannot silently reduce quality.

## Sources

- [Anthropic contextual retrieval](https://www.anthropic.com/engineering/contextual-retrieval), [techniques compared](https://blog.starmorph.com/blog/rag-techniques-compared-best-practices-guide), [advanced RAG techniques](https://atlan.com/know/advanced-rag-techniques/), [next-generation retrieval strategies](https://machinelearningmastery.com/beyond-vector-search-5-next-gen-rag-retrieval-strategies/), [RAG architectures field guide](https://dev.to/sreeraj-sreenivasan/rag-classifications-architectures-a-field-guide-for-production-grade-systems-p27)
- RAG for code: [AST-derived vs AI-extracted graphs (arXiv)](https://arxiv.org/abs/2601.08773v1), [why general retrieval fails on code](https://tianpan.co/blog/2026/05/07/code-specific-rag-general-retrieval-fails-codebases)
- Document parsing: [2026 tool comparison](https://themenonlab.blog/blog/best-open-source-pdf-to-markdown-tools-2026), [MarkItDown, Docling and PyMuPDF4LLM](https://docs.bswen.com/blog/2026-08-20-markitdown-docling-pymupdf4llm-comparison)

The cost ratings above are relative judgements, not measurements.
