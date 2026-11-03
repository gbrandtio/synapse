"""Made-up tickets for the retrieval benchmark.

Everything here is invented. No real Jira data appears in this repository.
"""

# (id, text)
TICKETS: list[tuple[str, str]] = [
    ("T1", "Login fails on Safari. After entering the password the page reloads and the session cookie is missing. Fixed by setting SameSite=None on the auth cookie."),
    ("T2", "Export to PDF cuts off the right column of invoices when the table has more than eight columns. Workaround: switch page orientation to landscape."),
    ("T3", "ERR_TIMEOUT_504 on the payments gateway during nightly settlement. Root cause: connection pool exhausted, raised max_connections from 20 to 80."),
    ("T4", "Password reset email never arrives for users on the corporate domain. The mail relay was rejecting messages because the SPF record was out of date."),
    ("T5", "Dashboard takes 40 seconds to load for accounts with more than 10,000 projects. Added an index on project.owner_id and paginated the widget query."),
    ("T6", "Mobile app crashes when the user rotates the screen during photo upload. Null pointer in UploadActivity after configuration change."),
    ("T7", "CSV import silently drops rows containing a semicolon in the description field. Parser now honours quoted fields."),
    ("T8", "Customers in Germany see prices without VAT at checkout. Tax rule for DE was missing after the catalogue migration."),
    ("T9", "Scheduled reports are sent twice on daylight saving change. Cron trigger now runs in UTC and converts for display."),
    ("T10", "Search returns no results when the query contains an apostrophe, such as O'Brien. Escaping fixed in the query builder."),
    ("T11", "Printer driver PX-400 stops responding after 200 labels. Firmware 2.1.7 resolves the buffer overflow."),
    ("T12", "Single sign-on loop with Okta when the clock on the server drifts by more than five minutes. Enabled NTP on all nodes."),
    ("T13", "Backup job fails with disk full on the Sydney node. Old snapshots were never rotated; added a 14 day retention policy."),
    ("T14", "Attachment upload limited to 2 MB although the setting says 25 MB. Reverse proxy client_max_body_size was the real limit."),
    ("T15", "Webhook retries flood the partner endpoint after an outage. Added exponential backoff with a ceiling of one hour."),
    ("T16", "Users cannot delete their own comments after the permissions refactor. Role check compared the wrong identifier."),
    ("T17", "Memory leak in the report worker: heap grows by 200 MB per hour. A cache of parsed templates was never evicted."),
    ("T18", "Dark mode makes the chart legend unreadable because the text stays black. Theme token applied to legend labels."),
    ("T19", "API returns HTTP 500 instead of 404 for a deleted customer. Missing null check in CustomerController.getById."),
    ("T20", "Barcode scanner input is lost when focus moves to the quantity field too quickly. Input is now buffered until focus settles."),
    ("T21", "Greek characters in customer names appear as question marks in exported invoices. Font embedding was missing from the PDF template."),
    ("T22", "Two-factor codes rejected for users whose phone clock is behind. Accepted window widened to one step either side."),
    ("T23", "Database migration 0042 locks the orders table for 20 minutes. Rewritten to add the column online and backfill in batches."),
    ("T24", "Notification badge keeps showing unread items after they are read on another device. Sync event was not broadcast."),
]

# (query, expected ticket id)
TICKET_QUERIES: list[tuple[str, str]] = [
    ("Why did people get logged out straight away in Safari?", "T1"),
    ("invoice pdf missing a column", "T2"),
    ("ERR_TIMEOUT_504", "T3"),
    ("customers not receiving reset password mail", "T4"),
    ("slow dashboard with many projects", "T5"),
    ("app crash when turning the phone sideways while sending a picture", "T6"),
    ("rows lost when importing a spreadsheet", "T7"),
    ("German tax not shown at payment", "T8"),
    ("report delivered two times when clocks change", "T9"),
    ("searching a surname like O'Brien finds nothing", "T10"),
    ("PX-400", "T11"),
    ("endless redirect during Okta login", "T12"),
    ("server ran out of space during backups", "T13"),
    ("can't attach files larger than 2 MB", "T14"),
    ("partner complaining about too many webhook calls after downtime", "T15"),
    ("worker process using more and more RAM", "T17"),
    ("CustomerController.getById", "T19"),
    ("orders table blocked during a schema change", "T23"),
]
