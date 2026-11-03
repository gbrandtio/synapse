# Connectors and external sources

Connections are always optional. Fetched data is stored, so assistants keep working when a source later becomes unreachable. Workflows never assume that a connection exists: Synapse checks availability when they run, and each Fetch step defines what happens if it fails.

## The connector contract

Every connector implements the same small interface, so adding one (Confluence, for example) touches nothing else.

```python
class Connector(Protocol):
    manifest: ConnectorManifest   # name, supported URLs, access methods, fields
    async def probe(self, target: Target) -> AccessReport: ...
    def list(self, target: Target, since: Cursor | None) -> AsyncIterator[ItemRef]: ...
    async def fetch(self, ref: ItemRef) -> Record: ...
```

`probe` is what makes the UI friendly. It answers: what is this link, can I reach it, how much is there, how long will it take, and what would make it better? For Jira and GitHub, it also lists the fields the user could capture.

## Source and record types

| Blueprint source `type` | Produces these record `source_type` values |
|---|---|
| `folder`, `file` | `document` |
| `web` | `web_page` |
| `github` | `repo_file`, `git_commit`, `github_issue`, `github_pull_request`, `github_release` |
| `local_git` | `repo_file`, `git_commit` |
| `jira` | `jira_issue` |
| `spreadsheet` | `jira_issue`, or `table_row` |

## The structured record

Every record has the same common part, plus a `fields` part that depends on its source type.

```json
{
  "schema": "synapse.record/v1",
  "id": "jira:acme.atlassian.net:issue:SUP-123",
  "source_type": "jira_issue",
  "title": "Login fails on Safari",
  "body_markdown": "...",
  "authors": ["..."],
  "created_at": "...",
  "updated_at": "...",
  "fields": {
    "status": "In Progress",
    "priority": "High",
    "assignee": "...",
    "start_date": "2026-03-01",
    "story_points": 5
  },
  "relations": [{ "type": "parent", "target": "jira:acme.atlassian.net:issue:SUP-100" }],
  "children": [
    { "kind": "comment", "author": "...", "created_at": "...", "body_markdown": "..." }
  ],
  "source": {
    "connector": "jira",
    "url": "https://acme.atlassian.net/browse/SUP-123",
    "access_method": "browser_session",
    "fetched_at": "...",
    "content_hash": "..."
  },
  "completeness": { "partial": false, "missing": [] },
  "trust": "external_untrusted"
}
```

Workflow steps receive these records as JSON, so an agent or prompt gets the same structure for every source. `completeness` tells the AI honestly when data is partial, so it can say so instead of guessing.

## Capturing different details per source

Each source type declares its fields, with a small definition of how each is used. `title`, `body_markdown` and `children` are common parts of every record, so the definition only says whether to embed them:

```yaml
source_type: jira_issue
fields:
  - { name: status,     type: keyword, filter: true,  show_to_ai: true }
  - { name: status_category, type: keyword, filter: true, show_to_ai: true }
  - { name: start_date, type: date,    filter: true,  show_to_ai: true }
  - { name: priority,   type: keyword, filter: true,  show_to_ai: true }
body: { embed: true }
children:
  - { kind: comment, embed: true }
```

For a Jira ticket, each detail is handled like this:

| Detail | Stored in | Searchable by meaning | Filter and count | AI sees it when |
|---|---|---|---|---|
| Summary and description | SQLite, and passages | Yes | No | That passage is found |
| Each comment | SQLite, and its own passage linked to the ticket | Yes | By author and date | That comment is found |
| Status, priority, assignee | SQLite `record_fields` table | No | Yes | Any passage of the ticket is found |
| Start date | SQLite `record_fields` table | No | Yes, such as "started after March" | Any passage of the ticket is found |
| Custom fields the user selects | Same as above, based on their type | Only if text | Yes, if not text | Any passage of the ticket is found |

This gives the behaviour the user would expect:

- A comment that says "fixed by restarting the server" can be found by meaning, and the AI still sees that it belongs to SUP-123, its status, and its start date.
- "Tickets that started after March" uses exact date filtering rather than guesswork.
- Sources do not interfere with each other. A Jira field is simply empty on a PDF passage, which costs almost nothing in a column store.

**Storage:** SQLite holds the full record and a `record_fields` table, which is the source of truth for counting and listing. Search filters read the same table, so nothing is copied and any number of fields works. Phase 0 tested this with 40 fields.

**Changing what is captured:** adding a filter field means fetching that field and adding a column, so existing embeddings are untouched. Adding text, such as turning on comments, embeds only the new text.

## Access order

For any source, Synapse picks the best method available and explains the choice:

| Source | Order |
|---|---|
| GitHub | Token or sign-in, then anonymous API for public repos, then a local git repo |
| Jira | Token, then anonymous API for public projects, then browser login, or an imported Excel or CSV export |
| Web pages | Reading the page directly |

## GitHub

**Link detection:** repo, branch or folder, file, issue, pull request, release, organisation, GitHub Enterprise host, or a local path.

| Data | Token | Public, no key | Local git repo |
|---|---|---|---|
| Code and docs | Tarball API | Tarball download, without using the API budget | Reads tracked files with Dulwich |
| Commits, branches, tags | REST | REST, budgeted | Reads the history with Dulwich |
| Issues, PRs, comments | REST and GraphQL | REST, budgeted | Not available, because git does not store them |

**Private repo with no token:** GitHub returns "not found" for a private repo, and this looks identical to a repo that does not exist. Synapse therefore offers both ways forward:

> We can't reach this repository. It may be private. **[Choose a local copy]** **[Add a token]**

**How a local git repo behaves:**

- **Read-only and offline:** Synapse never pulls, fetches, or changes the repo, and it needs no git install, network or GitHub account.
- **Freshness is visible:** it reads whatever is on disk, so the UI shows "Last commit: 3 days ago". The user updates the repo in their usual tool, and Synapse notices the change.
- **Link back:** if the repo's `origin` points to GitHub, citations can link to the file on GitHub, though the user may need to sign in there to open it.
- **Limits:** files stored with Git LFS appear only as pointers, so they are skipped and listed. Issues and PRs need a token, and the UI says so plainly rather than returning partial results.

Implementation details:

- **Getting a token:** "Sign in with GitHub" (OAuth device flow, which needs no client secret in the app) or a pasted fine-grained token. The device flow simply obtains an API token, and Synapse never reads GitHub through a browser session. An existing `gh` CLI login can be reused with the user's consent.
- **Rate limits:** without a key, GitHub allows 60 API requests an hour per IP address. Fetching 100 items per request and using repo-wide comment listing stretches this. When the budget runs out, the job pauses until the reset time and the UI offers "Add a token to speed this up".
- **Incremental sync:** uses `since` and ETags, and unchanged responses do not count against the limit.
- **Filtering:** tracked files only by default, skipping binaries, vendored folders and lockfiles. Repo content is read from the archive stream with path and size checks. For local repos, the *Include uncommitted files* setting adds untracked working files, and symlinks leading outside the repo are never followed.

## Jira

**Link detection:** Synapse identifies Cloud or Server/Data Center from `serverInfo`, then converts the link into a query. Users never have to write JQL.

| Link | Becomes |
|---|---|
| `/browse/SUP-123` | That one issue |
| `/projects/SUP` or a board link | `project = SUP`, or the board's filter |
| `/issues/?jql=...` or `?filter=123` | That query or saved filter |

| Access | Cloud | Server / Data Center |
|---|---|---|
| Key | Email and API token | Personal access token |
| No key, public | Anonymous REST | Anonymous REST |
| No key, private | Browser session calling REST from inside the page | Same |
| No access at all | Import an Excel or CSV export | Same |

**Browser login returns the same data as a token.** After the user signs in, Synapse calls Jira's own REST API from within that logged-in page, instead of scraping HTML. The same mapping code is used for both, so results are complete and do not break when the Jira UI changes.

Implementation details:

- **Search:** Cloud uses `/rest/api/3/search/jql`, because the old `/search` endpoints were removed. It uses token-based paging with no jumping to a page, so progress is stored as a resumable cursor.
- **Text format:** Cloud returns ADF, which is converted to Markdown. Server wiki markup is converted too.
- **Fields:** `/rest/api/3/field` provides each site's real field list for the "What to capture" picker. This matters for start date, which is often a custom field, and an agent then sees "Story Points" rather than `customfield_10016`.
- **Extra data:** comments and change history are fetched separately. Attachments are opt-in and pass through the normal document reader.
- **Sync:** queries for `updated >=` the last sync time, with a small overlap. A periodic key-list comparison finds deleted issues.
- **Rate limits:** low concurrency, and it obeys `429` and `Retry-After`.

## Importing Excel and CSV files

Some users only have a spreadsheet of Jira details, perhaps because a colleague exported it, or because their company allows no API access. Imported rows become normal `jira_issue` records, so comments, filters, counting and citations all work exactly as they do with a live connection.

**Supported files:** `.xlsx`, `.xlsm` (macros are ignored), `.csv`, and `.xls`. This includes older Jira exports that are really HTML files named `.xls`, so Synapse checks a file's content, not just its extension.

**What happens:**

1. **Recognise:** the user drops a file. Columns such as "Issue key", "Summary" and "Status" identify a Jira export, and Synapse offers "Import as tickets" or "Treat as a document".
2. **Match columns:** Synapse fills in a mapping that the user can correct. Repeated "Comment" columns become one list of comments. Columns with values become optional fields, and empty columns stay hidden.
3. **Check:** a preview shows the first rows as tickets, and lists problems in plain words, such as "12 rows have no issue key", "We can't tell if 03/04/2026 means March or April", or "2 people appear only as IDs".
4. **Import:** only changed rows are processed, using a hash of the columns being captured. Hashing the whole row would not work, because columns such as "Last Viewed" change without the ticket changing. The mapping is saved with the source, so re-importing a newer export takes one click.

This fragment belongs inside a [collection blueprint](./configuration.md#the-blueprints):

```yaml
sources:
  - type: spreadsheet
    path: ~/Documents/jira-export-november.xlsx
    import_as: jira_issue
    site: acme.atlassian.net      # optional, enables links back to Jira
    columns:
      key: "Issue key"
      title: "Summary"
      body: "Description"
      status: "Status"
      start_date: "Custom field (Start date)"
      comments: "Comment"         # all columns with this name are combined
    date_format: DD/MMM/YY h:mm A
    on_missing_rows: keep
```

**Handling messy files:**

| Situation | Behaviour |
|---|---|
| Comments are missing from the export | The sample includes comments, but other export types may not, so Synapse detects this per file. It sets `completeness.missing: ["comments"]`, and tells the user |
| Exactly 1,000 rows | One guide reports a 1,000-row limit on a single export, so Synapse warns that the file may be cut off |
| Comment cells hold date, author and text together | Split into their parts when recognised, otherwise kept as text. See the format below |
| Several sheets, or a title above the headers | The user picks the sheet, and Synapse detects the header row |
| Formulas | Synapse reads the last calculated value, and never calculates or runs anything |
| Rows disappear in a newer file | Kept by default, because exports are often filtered. The user can choose to remove them |
| Very large or malformed files | Reading happens in the time-limited parser worker, with size limits that also protect against zip bombs. `defusedxml` is required, because `openpyxl` needs it to guard against XML entity-expansion attacks |

**Freshness and duplicates:** a spreadsheet is a snapshot, so records use `access_method: file_import`, and answers state the file's date. If the same issue key arrives from a Jira connection and a spreadsheet for the same site, one record is kept, using the newer "Updated" value. Exports have no time zone, so the connection's record wins unless the file's value is more than a day newer.

### What a real export looks like

These rules come from one real Jira Cloud CSV export, examined on 2026-11-03. It has 29 tickets from one project and 475 columns. It is the only export available, so the importer is designed around it. `.xlsx`, `.xls` and Data Center exports are still supported, on the assumption that they use similar columns. If one differs, the mapping screen lets the user correct it, and the preview lists the problems before anything is imported.

| What the export contains | What Synapse does |
|---|---|
| **Mostly empty columns:** 394 of the 475 columns have no value in any row, and many others hold internal data | The mapping screen hides empty columns, and pre-selects only the known ones. Columns holding internal data, such as `{}` or rank codes, are left unselected. A later import that fills a hidden column shows it as new |
| **Comment cells:** each one is `date;author ID;text`, and the text can contain semicolons and line breaks | It splits at the first two semicolons only, and keeps the rest as the text |
| **People as IDs:** comments and `[~accountid:...]` mentions use account IDs, not names | It builds an ID-to-name list from column pairs such as "Assignee" and "Assignee Id". Repeated columns such as "Watchers" and "Watchers Id" are paired by position. In the sample, this named all 50 comments, but two of the five authors could be named only because they were also watchers. Any author missing from these columns appears as "Unknown person", and `completeness.missing` records this |
| **Repeated column names with two meanings:** "Comment" and "Labels" hold several values, while two "Custom field (Source)" columns are different fields | Only known multi-value names, such as "Comment", "Labels" and "Attachment", are combined into one list. Other repeated names stay separate, because the file cannot show whether they are one field or two. The preview offers to combine them |
| **Similar names:** "Status" and "Custom field (Status)", "Comment" and "Custom field (Comments)" | Exact names are matched first, and the "Custom field (...)" wrapper is removed only for display. Start date is a custom field here, and it is empty on every row, so the sample does not confirm how start dates import. Tests use made-up files with start dates filled in |
| **Dates:** `03/Nov/26 2:15 PM` style, with a month name, a two-digit year and no time zone. One column uses another format | The month name means no question is needed. The format is detected per column, and the computer's time zone is assumed. Answers therefore state dates, and exact times may be off if someone elsewhere made the export. Only English month names are supported |
| **Text format:** Jira wiki markup, even though Cloud's API returns ADF | The Server wiki markup converter is used for Cloud exports too |
| **Attachments:** cells list `date;author ID;file name;link`, but not the file | The date and author are read from the left and the link from the right, so a semicolon in a file name is safe. Names and links are kept. The files cannot be read from the export, so the Attachments setting needs a connection |
| **Useful extras:** "Status category", "Parent key", "Inward issue link (...)" and Jira links in attachment cells | Status category answers "how many are open?" whatever a project calls its statuses. Parent and link columns become `relations`, though the sample has only inward links, so outward links are unconfirmed. The site is filled in from the links when present |
| **Same value on every row:** such as "Project description" | Known project-level columns, such as project name, description and lead, are stored once for the project and never embedded per ticket. Ticket fields always stay on each record, even when every row has the same value, because a filtered export can make Status or Priority look constant |
| **File format:** UTF-8 with a byte order mark, rows ending in LF, mostly LF with a few CRLF line breaks inside cells, and a 23,000-character cell | It uses a real CSV parser that handles the byte order mark and line breaks inside cells. It raises Python's default limit of about 131,000 characters per cell to 16 MB, inside the parser worker. A larger cell stops the import with a plain message naming the row |
| **Personal data:** names, account IDs and email addresses | It stays on the computer unless a cloud AI is used. Remove secrets from content does not hide names or email addresses, so the import preview says that these will be stored |

**Other spreadsheets:** the same importer can map any table to a `table_row` record, which also makes them filterable and countable. Spreadsheets that are not tabular data remain ordinary documents.

## Browser login rules (Jira only)

- **Dedicated profile:** it uses the user's installed Chrome or Edge with a separate Synapse profile. The user's normal profile and passwords are never touched.
- **User logs in:** login, SSO and MFA happen entirely in a visible window. Cookies stay in that profile and are never exported.
- **Read-only:** GET requests only, restricted to the host the user connected, and throttled.
- **No bypassing:** if a CAPTCHA or security challenge appears, Synapse stops and asks the user. It never tries to get around it.
- **Clear expectations:** the UI explains that some company policies do not allow this, and that a token is the more reliable option. Expired sessions show a "Sign in again" card, and assistants continue with the stored data meanwhile.

## Other sources

A generic web connector uses `httpx` and `trafilatura`, follows `robots.txt`, and blocks private network addresses unless the user approves that host, which covers intranet Jira. It resolves each hostname, connects only to the address it checked, and repeats the check on every redirect, so DNS rebinding and redirects cannot bypass the block.

## Sources

- Jira: [enhanced search migration](https://tnckb94959.lithium.com/forums/Jira-articles/Avoiding-Pitfalls-A-Guide-to-Smooth-Migration-to-Enhanced-JQL/ba-p/2985433), [removed endpoint reports](https://community.atlassian.com/forums/Jira-questions/Rest-API-won-t-work/qaa-p/3113549), [comment columns (forum)](https://community.atlassian.com/forums/discussion/2182942/how-can-i-export-comments-in-the-issues), [export guide](https://skyvia.com/blog/jira-export-to-csv/)
- GitHub: [REST API rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

**Not yet confirmed against official sources:** GitHub's ETag and tarball behaviour, GitHub's "not found" response for private repos, Jira anonymous REST behaviour, and the HTML-as-`.xls` Jira export. Contract tests must confirm these before they are relied on.
