"""The HTTP API, reachable only from this computer with the per-launch token."""

from __future__ import annotations

import hmac
import logging
from collections.abc import AsyncIterable, AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from synapse_engine.application.ingest import IngestDocument, IngestFinished, IngestProgress
from synapse_engine.application.ports import (
    Answerer,
    CitationsEvent,
    KnowledgeStore,
    NotFoundEvent,
    TokenEvent,
)
from synapse_engine.domain.models import Document, UnreadableDocumentError

logger = logging.getLogger(__name__)
_GENERIC_ERROR = "Something went wrong. Please try again."


class AddDocumentRequest(BaseModel):
    """A file on this computer to add."""

    path: str = Field(min_length=1, max_length=4096)


class AskRequest(BaseModel):
    """A question to answer."""

    question: str = Field(min_length=1, max_length=4000)


class DocumentResponse(BaseModel):
    """A stored document."""

    id: int
    name: str
    pages: int
    passages: int

    @classmethod
    def of(cls, document: Document) -> DocumentResponse:
        """Map a domain document to its response."""
        return cls(
            id=document.id,
            name=document.name,
            pages=document.pages,
            passages=document.passages,
        )


class Services:
    """The use cases the API calls."""

    def __init__(
        self,
        ingest: IngestDocument,
        answerer: Answerer,
        store: KnowledgeStore,
        on_shutdown: Callable[[], None] = lambda: None,
    ) -> None:
        self.ingest = ingest
        self.answerer = answerer
        self.store = store
        self.on_shutdown = on_shutdown


def _error_event(message: str) -> ServerSentEvent:
    return ServerSentEvent(data={"message": message}, event="error")


async def _ingest_events(services: Services, path: Path) -> AsyncIterator[ServerSentEvent]:
    try:
        async for event in services.ingest.run(path):
            match event:
                case IngestProgress():
                    data = {"message": event.message, "done": event.done, "total": event.total}
                    yield ServerSentEvent(data=data, event="progress")
                case IngestFinished():
                    data = {
                        "document": DocumentResponse.of(event.document).model_dump(),
                        "already_present": event.already_present,
                    }
                    yield ServerSentEvent(data=data, event="finished")
    except UnreadableDocumentError as error:
        yield _error_event(str(error))
    except Exception:
        logger.exception("Adding a document failed")
        yield _error_event(_GENERIC_ERROR)


async def _answer_events(
    services: Services, question: str, safe_errors: tuple[type[Exception], ...]
) -> AsyncIterator[ServerSentEvent]:
    try:
        async for event in services.answerer.answer(question):
            match event:
                case TokenEvent():
                    yield ServerSentEvent(data={"text": event.text}, event="token")
                case CitationsEvent():
                    citations = [
                        {
                            "number": c.number,
                            "document_name": c.document_name,
                            "page": c.page,
                            "text": c.text,
                            "is_inferred": c.is_inferred,
                        }
                        for c in event.citations
                    ]
                    yield ServerSentEvent(data={"citations": citations}, event="citations")
                case NotFoundEvent():
                    yield ServerSentEvent(data={"message": event.message}, event="not_found")
    except safe_errors as error:
        yield _error_event(str(error))
    except Exception:
        logger.exception("Answering a question failed")
        yield _error_event(_GENERIC_ERROR)


def create_app(
    services: Services,
    token: str,
    safe_errors: tuple[type[Exception], ...] = (),
) -> FastAPI:
    """Build the API. Every route needs the per-launch token."""
    expected = f"Bearer {token}".encode()

    def require_token(authorization: Annotated[str | None, Header()] = None) -> None:
        if not hmac.compare_digest((authorization or "").encode(), expected):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        services.on_shutdown()

    app = FastAPI(
        title="Synapse Engine",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(require_token)],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/documents")
    async def list_documents() -> list[DocumentResponse]:
        return [DocumentResponse.of(d) for d in await services.store.list_documents()]

    @app.post("/documents", response_class=EventSourceResponse)
    async def add_document(body: AddDocumentRequest) -> AsyncIterable[ServerSentEvent]:
        async for event in _ingest_events(services, Path(body.path)):
            yield event

    @app.post("/ask", response_class=EventSourceResponse)
    async def ask(body: AskRequest) -> AsyncIterable[ServerSentEvent]:
        async for event in _answer_events(services, body.question, safe_errors):
            yield event

    return app
