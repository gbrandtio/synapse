"""Hand-written questions about this repo's docs, with the section that answers them."""

PROSE_QUERIES: list[tuple[str, str]] = [
    ("Why is SQLite used instead of PostgreSQL on the desktop?", "0004-sqlite-and-lancedb-for-desktop#Context"),
    ("What happens when the bundled installer goes over the size limit?", "0010-bundled-models-and-github-limits#Decision"),
    ("Can a poisoned ticket make the agent change something?", "0011-read-only-actions#Context"),
    ("How do variables get inserted into a prompt safely?", "0012-safe-prompt-filling#Decision"),
    ("What warnings do users see because builds are not signed?", "0013-unsigned-first-builds#Consequences"),
    ("Why not use different RAG methods for different sources?", "0005-one-rag-pipeline-with-collections#Context"),
    ("How does Synapse handle Jira comments and start dates?", "connectors#Capturing different details per source"),
    ("How can a private repository be read without a token?", "connectors#GitHub"),
    ("What does the first-run screen look like?", "ux#First run (under a minute)"),
    ("How are exact counts of open tickets produced?", "rag-pipeline#Counting and listing questions"),
    ("What are the three levels of settings?", "configuration#Three levels of settings"),
    ("How does the app start the Python engine?", "overview#How the app starts the engine"),
]
