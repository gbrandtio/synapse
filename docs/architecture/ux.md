# UI and UX

## Principles

- **Plain words:** the UI says "Collection", "Passage" and "Assistant", and never "vector store", "embedding" or "JQL" outside Expert mode.
- **Working result first:** an assistant can answer within minutes, and options come afterwards.
- **Good defaults, explained:** every setting has a default and a one-sentence description, as listed in [Every setting](./configuration.md#every-setting), and users never have to choose a RAG method.
- **Useful errors:** each one says what happened and offers one button to fix it.
- **Visible trust:** every answer shows its sources, and every source shows its status and last sync.

## First run (under a minute)

With Complete there are no setup questions. The user goes straight to creating an assistant, using the bundled private AI:

```
┌ Welcome to Synapse ───────────────────────────────────────────┐
│ ✓ Your private AI is ready. It runs on this computer.         │
│                                                               │
│ You can use better AI later:                                  │
│   • This computer has 16 GB of memory. A larger model would   │
│     give better answers (3 GB download).        [ Get it ]    │
│   • Use a cloud AI, if you have a key.          [ Add key ]   │
│                                                               │
│                                  [ Create my first assistant ]│
└───────────────────────────────────────────────────────────────┘
```

Synapse checks the computer's memory and warns if it is below what the bundled model needs. With Standard, the first screen instead offers a cloud key, the user's own Ollama if found (not built yet), or a model download.

## Creating an assistant

**Step 1: pick a template.** The cards are the [starter templates](./workflows-and-prompts.md), plus "Start from scratch".

**Step 2: choose knowledge.** The user picks existing collections or creates one, and all source types are added on one screen.

```
┌ What should your assistant know? ─────────────────────────────┐
│  Collection name: [ Support tickets                         ] │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │     Drop files or folders here, or click to browse      │  │
│  └─────────────────────────────────────────────────────────┘  │
│  Or paste a link: [ https://acme.atlassian.net/browse/SUP   ] │
│                                                               │
│  ✓ Jira project "Support", about 1,240 issues                 │
│    This project is private. How do you want to connect?       │
│    [ Sign in with browser ]  [ Use an API token ]             │
│    Capturing: status, assignee, comments        [ Change ]    │
│                                                               │
│  ✓ Manuals folder, 86 files                                   │
│  ✓ jira-export.xlsx, Jira export with 340 tickets             │
│    [ Check columns ]                                          │
│  ⚠ github.com/acme/app: public, full code available.          │
│    Issues would take about 2 hours without a token. [Add one] │
│  ⚠ github.com/acme/private: can't reach this. It may be       │
│    private. [ Choose a local copy ]  [ Add a token ]          │
└───────────────────────────────────────────────── [ Continue ] ┘
```

The link box runs `probe` as soon as a link is pasted, so users learn what will happen before anything starts.

**What to capture** opens a list of the source's real fields:

```
┌ What should we keep from this Jira project? ──────────────────┐
│ ☑ Comments        Conversations on each ticket. Searchable.   │
│ ☑ Status          Lets you ask for open or closed tickets.    │
│ ☑ Assignee        Lets you ask who is working on what.        │
│ ☑ Start date      Lets you ask for tickets by start date.     │
│ ☐ Story Points    Custom field in your Jira.                  │
│ ☐ Attachments     Reads attached files. Takes longer.         │
└───────────────────────────────────────────────────────────────┘
```

**Check columns** shows how a spreadsheet will be read:

```
┌ jira-export.xlsx: Sheet "Issues", 340 rows ───────────────────┐
│ Your column        Used as           Example                  │
│ Issue key       →  Ticket number     SUP-123                  │
│ Summary         →  Title             Login fails on Safari    │
│ Status          →  Status            In Progress              │
│ Start date      →  Start date        03/04/2026               │
│ Comment (x6)    →  Comments          6 columns combined       │
│ Team            →  [ Custom field ▾] Payments                 │
│                                                               │
│ ⚠ Does 03/04/2026 mean:  ( ) 3 April   ( ) March 4            │
│ ⚠ 12 rows have no issue key and will be skipped.  [ Show ]    │
│ Empty columns are hidden.                         [ Show ]    │
│                                              [ Import 328 ]   │
└───────────────────────────────────────────────────────────────┘
```

The hidden-columns line matters because a real Jira export can have hundreds of columns, most of them empty.

**Step 3: build.** Progress runs in the background, and the user can start chatting with what is already ready.

**Step 4: try it.**

```
┌ Support helper ─────────────────────────────┬ Sources ─────────┐
│ You: How do I reset a user's password?      │ [1] Admin Guide  │
│                                             │     page 42      │
│ To reset a password, open Users, then       │ [2] SUP-881      │
│ choose Reset [1]. This was changed in       │     Done         │
│ version 4.2 [2].                            │ Synced today     │
│                                             │ [Why this answer]│
│ 👍 👎  Copy                                 │                  │
│ [ Ask something...                        ] │                  │
└─────────────────────────────────────────────┴──────────────────┘
```

"Why this answer" shows the passages found and how they ranked, which also helps users diagnose bad answers.

## Editing a prompt

```
┌ Step 2 of 3: Ask AI ──────────────────────────────────────────┐
│ What should the AI do?                 [ Prompt library ▾ ]   │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ You are a friendly support agent for Acme.                │ │
│ │ Customer question: [question]                             │ │
│ │ Relevant information: [Search results]                    │ │
│ │ Reply in under 150 words.                                 │ │
│ └───────────────────────────────────────────────────────────┘ │
│ Insert: [question] [today] [Search results] [Fetched records] │
│                                                               │
│ ☑ Show sources                                                │
│ [ Test this step ]  [ History ]  [ Reset to template ]        │
└───────────────────────────────────────────────────────────────┘
```

## Main areas

| Area | Contents |
|---|---|
| Assistants | Cards with name, last used, and health status |
| Collections | One card per collection with its sources and test score. Opening one shows each source's status, last sync, skipped items, and a sync button |
| Automations | Step list, run history, and approvals waiting for the user |
| Prompts | The saved prompt library |
| Connections | Optional links to GitHub, Jira and AI providers, each with sign-in state and a Test button |
| Settings | Every setting with its description, filtered by the chosen level, including privacy and storage used |

The step editor is a vertical list of cards with a "+" between them, and each card is a plain form generated from the blueprint schema.

Accessibility is included from the start: keyboard navigation, screen-reader labels, and light and dark themes. The app is English only, as [ADR 0014](../adr/0014-english-only-windows-and-mac.md) explains.
