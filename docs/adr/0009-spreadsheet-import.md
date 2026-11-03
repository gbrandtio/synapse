# 0009. Import Jira details from Excel and CSV as normal records

- Status: Accepted
- Date: 2026-11-03
- Deciders: Project owner

## Context

Some users only have exported spreadsheets of Jira details.

## Decision

A mapping-driven importer turns `.xlsx`, `.xlsm`, `.csv` and `.xls` rows into `jira_issue` records. It recognises Jira exports, and lets the user correct column mappings and unclear dates. Cell values only are read, and macros and formulas never run. The same importer can produce generic `table_row` records.

## Consequences

Filters, comments, counting and citations all work on imported data. Only one real export is available, a Jira Cloud CSV, so the importer is designed around it, and other formats rely on the mapping screen and preview if they differ. Real exports hold personal and company data, so they stay out of git, and committed tests use made-up data in the same format. That export changed several import rules, which [What a real export looks like](../architecture/connectors.md#what-a-real-export-looks-like) records. Imported data is a snapshot, so answers state its date.

## Alternatives considered

- **Treat spreadsheets only as documents:** Filtering and counting would not work.
- **Require a Jira connection:** It would exclude users with only a file.
