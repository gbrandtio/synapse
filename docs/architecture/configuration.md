# Configuration

## The blueprints

There are two kinds of blueprint, both versioned YAML files validated by Pydantic. A JSON Schema generated from them is also used to build forms in the UI, including each setting's description.

A **collection** says what content is gathered:

```yaml
schema_version: 1
kind: collection
name: Support tickets
description: Customer problems and how they were solved
sources:
  - type: jira
    url: https://acme.atlassian.net/browse/SUP
    sync: hourly
    capture: [status, assignee, start_date, comments]
```

An **assistant** says which collections it may use and what it does with them:

```yaml
schema_version: 1
kind: assistant
name: Support helper
model: { provider: ollama, name: "<from catalog>" }
steps:
  - id: search
    type: search_knowledge
    collections: [support-tickets, product-manuals]
  - id: answer
    type: ask_ai
    prompt: |
      You are a friendly support agent for Acme.
      Customer question: {{question}}
      Relevant information: {{steps.search.results}}
      Reply in under 150 words.
    citations: required
```

Blueprints never contain secrets. Secrets are stored in the OS keychain and referenced by name.

An assistant can be exported as a `.synapse` file, with its collection definitions included. Double-clicking that file opens a review of what it contains, including prompts, the AI endpoint, sources and hosts. Nothing runs until the user confirms, and the app asks for whatever is missing, such as keys or local folders. See [Custom prompts](./workflows-and-prompts.md#custom-prompts).

The list of available models is a data file, so it can be updated without changing code.

## Three levels of settings

Users only see the level they choose.

- **Simple:** only the essentials, and everything else uses its default.
- **Advanced:** adds tuning options in plain language.
- **Expert:** adds the remaining options, and lets users edit the YAML directly with live validation.

## Every setting

The description below also appears beside each setting in the UI. Numeric defaults are starting points, and Phase 2 tunes them against the test sets. Unless "Next step" says otherwise, a change applies immediately. Internal engine values, such as `OLLAMA_HOST` or `num_ctx`, are not user settings, so they are not listed here.

**AI**

| Setting | What it does | Default | Level | Next step |
|---|---|---|---|---|
| AI provider | Chooses who writes the answers: a model on this computer, or a cloud service. | This computer in Complete, otherwise chosen at first run | Simple | |
| AI model | Chooses the specific model. Larger models usually answer better, but are slower or cost more. | The bundled small model in Complete | Simple | |
| Local AI engine | Chooses between Synapse's built-in Ollama and a copy of Ollama you installed yourself. | Built-in, or your own if Standard finds one | Advanced | |
| API key | The password that lets Synapse use a cloud AI service. It is stored in the system keychain. | None | Simple | |
| Creativity | Low gives consistent, factual answers, and high gives more varied wording. Low suits document questions. | Low (0.2) | Advanced | |
| Maximum answer length | Limits how long an answer can be, which also limits cost. | 1,000 tokens (about 750 words) | Advanced | |
| Embedding model | The model that converts text to numbers so that similar meanings can be found. It is shared across all collections. | The bundled model, chosen in Phase 0 | Expert | Reprocesses all collections |

**Collections and sources**

| Setting | What it does | Default | Level | Next step |
|---|---|---|---|---|
| Name and description | Identifies the collection. The description also helps people and the AI understand what it contains. | None | Simple | |
| Sources | The files, folders, links and repositories in the collection. | None | Simple | Fetches new content |
| What to capture | Chooses which details to keep from a source, such as Jira comments or start date. It lists the fields that the source really has. | Common fields, by source type | Simple | Re-fetches. New text gets embedded |
| Sync schedule | How often Synapse checks for changes: manually, hourly, daily, or when a local folder changes. | Manual | Simple | |
| Include and exclude patterns | Chooses which files to read or skip, such as skipping `*.log`. | Sensible skip list | Advanced | Updates the affected files |
| Maximum items | Stops very large sources from taking too long by setting an upper limit. | No limit, with a warning above 50,000 | Advanced | |
| Document reading quality | Fast reads ordinary documents quickly. High-quality handles scans and complex tables, but is slower and needs a download. Automatic chooses for each file. | Automatic | Advanced | Re-reads documents |
| Attachments | Whether files attached to tickets are also read. It appears in the What to capture list. | Off | Simple | Fetches attachments |
| Branch | The Git branch to read code from. | The default branch | Advanced | Updates changed files |
| Include uncommitted files | For local repositories, also reads files that have not been committed yet. | Off | Advanced | Updates changed files |
| History limit | How many past commits to read from a repository. | 500 | Advanced | Fetches or removes commits |
| Jira scope | Which tickets to include, using simple filters such as project, status and date. Any link the user pastes fills this in. | From the pasted link | Simple | Fetches changes |
| Import as | Whether a spreadsheet becomes tickets, table rows, or a plain document. Tickets and rows allow filtering and counting. | Detected from the columns | Simple | Re-imports the file |
| Column mapping | Which spreadsheet column holds which detail, such as "Issue key" or "Start date". | Matched automatically | Simple | Re-imports the file |
| Sheet and header row | Which sheet to read, and which row holds the column names. | Detected from the file | Advanced | Re-imports the file |
| Date format | How to read dates such as 03/04/2026, which could mean March or April. | Detected, and asked when unclear | Simple | Re-imports the file |
| If rows disappear | What happens when a re-imported file no longer has a row. Keeping is safer, because exports are often filtered. | Keep the record | Advanced | |

**Connections**

| Setting | What it does | Default | Level | Next step |
|---|---|---|---|---|
| GitHub token | Lets Synapse read private repositories, issues and pull requests, and raises GitHub's request limit. Obtained by signing in or by pasting one. Stored in the system keychain. | None | Simple | |
| GitHub Enterprise address | The address of a company's own GitHub server. | github.com | Advanced | |
| Jira address | Your Jira site, such as `acme.atlassian.net`. Filled in from a pasted link. On a spreadsheet import, it enables links back to Jira. | From the link | Simple | |
| Jira email and API token | Lets Synapse read private Jira Cloud projects. Stored in the system keychain. | None | Simple | |
| Jira personal access token | The same, for a company's own Jira Server or Data Center. | None | Simple | |
| Jira browser login | Reads private Jira through a one-time sign-in window. Sign in again when the session expires. | Off until used | Simple | Downloads the browser pack |
| Approved internal hosts | Private network addresses Synapse may reach, such as an intranet Jira. | None | Advanced | |

**Splitting (per source type)**

| Setting | What it does | Default | Level | Next step |
|---|---|---|---|---|
| Passage size | How much text goes in one searchable piece. Smaller is more precise, and larger keeps more context. | 500 tokens (about 375 words) | Advanced | Reprocesses that source type |
| Passage overlap | How much text consecutive passages share, so that ideas at a boundary are not lost. | 60 tokens | Expert | Reprocesses that source type |

**Search (per Search knowledge step)**

| Setting | What it does | Default | Level |
|---|---|---|---|
| Collections to search | Which collections this step may look in. | All in the assistant | Simple |
| Passages to consider | How many candidates are collected before the best are chosen. More finds more, but is slower. | 40 | Advanced |
| Passages given to the AI | How many of the best passages the AI reads. More gives more context, but costs more and can distract it. | 6 | Advanced |
| Meaning or exact words | The balance between finding similar meanings and matching exact words, set as weights when the two result lists are merged. Exact words help with codes, names and errors. | Mostly meaning, with more exact matching when a question looks like an exact term | Expert |
| Careful re-ranking | Uses a second model to reorder the best results. It adds a short delay to each answer, and testing has not yet shown a clear gain. | Off | Advanced |
| Include surrounding section | Gives the AI the whole section around each passage, which helps it understand what it found. | On | Advanced |
| Mix of sources | Stops one source type from filling all the results, so that a thousand tickets cannot crowd out a manual. | Up to 70% from one source type | Expert |
| Prefer recent content | Ranks newer content higher, which suits tickets more than manuals. | On for tickets and commits, off otherwise | Advanced |
| Retry with reworded question | If the results look weak, rewords the question and searches once more. It takes one extra AI call. | On | Advanced |
| Minimum confidence | How sure Synapse must be before answering. Higher means fewer wrong answers, but more "I couldn't find this" replies. | Medium | Advanced |

**Answers and prompts**

| Setting | What it does | Default | Level |
|---|---|---|---|
| Prompt | The instructions the AI follows in this step, written in the user's own words. See [Custom prompts](./workflows-and-prompts.md#custom-prompts). | From the template | Simple |
| Show sources | Requires the answer to link to the passages it relied on. When on, the app enforces this whatever the prompt says. Stored as `citations`. | On | Simple |
| Not-found message | What the assistant says when it finds nothing reliable. | "I couldn't find this in your documents." | Advanced |
| Internal prompts | The instructions for rewording questions and for checking results. Most people should leave these alone. | Built in | Expert |

**Workflow limits**

| Setting | What it does | Default | Level |
|---|---|---|---|
| Spending limit per run | Stops a run before its cloud AI cost exceeds this amount. | $1 | Simple |
| Maximum agent steps | How many actions an Agent step can take before it must finish, which prevents endless loops. | 10 | Advanced |
| Time limit per run | Stops a run that takes too long. | 10 minutes | Advanced |
| Schedule | When an automation runs: manually, at set times, or when a collection changes. It only runs while Synapse is open. | Manual | Simple |
| If a source can't be reached | Whether a Fetch step continues with the last synced data, with a visible note, or stops the run. | Use last synced data | Simple |

**Privacy and app**

| Setting | What it does | Default | Level |
|---|---|---|---|
| Never send data off this computer | Blocks all cloud AI and only allows local models. Connections to the sources you added still work. | On in Complete until a cloud AI is added | Simple |
| Remove secrets from content | Skips key files and hides passwords or keys found in text before they are stored or sent to AI. | On | Advanced |
| Usage statistics | Sends anonymous statistics about how the app is used, to help improve it. | Off | Simple |
| Data location | The folder where Synapse keeps its data. | Standard app data folder | Advanced |
| Keep running in the background | Keeps a tray icon so that schedules and syncs continue with the window closed. | Off | Simple |
| Start at login | Opens Synapse when the computer starts, which is useful for schedules. | Off | Advanced |
| Settings level | Chooses how many settings are visible: Simple, Advanced or Expert. | Simple | Simple |
| Appearance | Light, dark, or matching the system. | Match system | Simple |

## Status of these values

The defaults are starting points, not tested results. Phase 2 tunes them against the test sets described in [Measuring quality](./rag-pipeline.md#measuring-quality).
