from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from synapse_engine.adapters.ai.ask_graph import GraphAnswerer
from synapse_engine.adapters.ai.llama_process import LocalAiUnavailableError
from synapse_engine.adapters.parsers.pdf import PdfReader
from synapse_engine.adapters.stores.sqlite_store import SqliteKnowledgeStore
from synapse_engine.api.app import Services, create_app
from synapse_engine.application.ingest import IngestDocument
from tests.conftest import write_pdf

AUTH = {"Authorization": "Bearer secret"}


def events(body: str) -> list[tuple[str, dict]]:
    found = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in fields:
            found.append((fields["event"], json.loads(fields["data"])))
    return found


def client(tmp_path, embedder, factory=None, shutdown=lambda: None) -> TestClient:
    store = SqliteKnowledgeStore(tmp_path / "s.db")

    async def default_factory():
        return GenericFakeChatModel(messages=iter([AIMessage("Fourteen days [1].")]))

    services = Services(
        ingest=IngestDocument(PdfReader(), embedder, store),
        answerer=GraphAnswerer(embedder, store, factory or default_factory),
        store=store,
        on_shutdown=shutdown,
    )
    return TestClient(create_app(services, "secret", (LocalAiUnavailableError,)))


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "Bearer sécret"}]
)
def test_routes_need_the_token(tmp_path, embedder, headers) -> None:
    with client(tmp_path, embedder) as c:
        assert (
            c.get("/health", headers={k: v.encode() for k, v in headers.items()}).status_code == 401
        )
        assert (
            c.get("/documents", headers={k: v.encode() for k, v in headers.items()}).status_code
            == 401
        )


def test_api_docs_are_not_exposed(tmp_path, embedder) -> None:
    with client(tmp_path, embedder) as c:
        assert c.get("/docs", headers=AUTH).status_code == 404
        assert c.get("/openapi.json").status_code == 404


def test_bare_token_without_the_scheme_is_refused(tmp_path, embedder) -> None:
    with client(tmp_path, embedder) as c:
        assert c.get("/health", headers={"Authorization": "secret"}).status_code == 401


def test_drop_a_pdf_then_ask_and_get_a_cited_answer(tmp_path, embedder) -> None:
    pdf = write_pdf(tmp_path / "guide.pdf", ["how long are backups kept fourteen days"])
    with client(tmp_path, embedder) as c:
        added = events(c.post("/documents", headers=AUTH, json={"path": str(pdf)}).text)
        assert added[0][0] == "progress"
        assert added[-1][0] == "finished"
        assert added[-1][1]["document"]["name"] == "guide.pdf"
        assert c.get("/documents", headers=AUTH).json()[0]["passages"] == 1

        answer = events(
            c.post("/ask", headers=AUTH, json={"question": "how long are backups kept"}).text
        )
        text = "".join(d["text"] for kind, d in answer if kind == "token")
        assert text == "Fourteen days [1]."
        assert answer[-1][0] == "citations"
        assert answer[-1][1]["citations"][0]["document_name"] == "guide.pdf"
        assert answer[-1][1]["citations"][0]["page"] == 1


def test_unreadable_file_returns_a_friendly_event(tmp_path, embedder) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"nope")
    with client(tmp_path, embedder) as c:
        result = events(c.post("/documents", headers=AUTH, json={"path": str(bad)}).text)
    assert result[-1][0] == "error"
    assert "damaged" in result[-1][1]["message"]


def test_local_ai_failure_message_reaches_the_user(tmp_path, embedder) -> None:
    async def broken():
        raise LocalAiUnavailableError("The local AI did not start in time.")

    pdf = write_pdf(tmp_path / "a.pdf", ["how long are backups kept"])
    with client(tmp_path, embedder, broken) as c:
        c.post("/documents", headers=AUTH, json={"path": str(pdf)})
        result = events(
            c.post("/ask", headers=AUTH, json={"question": "how long are backups kept"}).text
        )
    assert result[-1] == ("error", {"message": "The local AI did not start in time."})


def test_unexpected_failure_hides_details(tmp_path, embedder) -> None:
    async def broken():
        raise RuntimeError("secret path /Users/someone")

    pdf = write_pdf(tmp_path / "a.pdf", ["how long are backups kept"])
    with client(tmp_path, embedder, broken) as c:
        c.post("/documents", headers=AUTH, json={"path": str(pdf)})
        result = events(
            c.post("/ask", headers=AUTH, json={"question": "how long are backups kept"}).text
        )
    assert result[-1][0] == "error"
    assert "secret" not in result[-1][1]["message"]


def test_empty_question_is_rejected(tmp_path, embedder) -> None:
    with client(tmp_path, embedder) as c:
        assert c.post("/ask", headers=AUTH, json={"question": ""}).status_code == 422


def test_shutdown_stops_local_ai(tmp_path, embedder) -> None:
    stopped: list[int] = []
    with client(tmp_path, embedder, shutdown=lambda: stopped.append(1)):
        assert stopped == []
    assert stopped == [1]
