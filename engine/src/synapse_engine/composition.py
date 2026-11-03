"""Wire the real adapters to the use cases."""

from __future__ import annotations

import httpx
from fastapi import FastAPI
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from synapse_engine.adapters.ai.ask_graph import GraphAnswerer
from synapse_engine.adapters.ai.embedder import FastEmbedEmbedder
from synapse_engine.adapters.ai.llama_process import LlamaProcess, LocalAiUnavailableError
from synapse_engine.adapters.parsers.pdf import PdfReader
from synapse_engine.adapters.stores.sqlite_store import SqliteKnowledgeStore
from synapse_engine.api.app import Services, create_app
from synapse_engine.application.ingest import IngestDocument
from synapse_engine.settings import Settings

_TEMPERATURE = 0.2
_MAX_ANSWER_TOKENS = 1000
_CONTEXT_TOKENS = 8192  # Holds six 500-token passages, the question and the answer.


def build_app(settings: Settings, token: str) -> FastAPI:
    """Create the API with real storage, models and parsers."""
    store = SqliteKnowledgeStore(settings.database)
    embedder = FastEmbedEmbedder(settings.embedding_dir)
    pid_file = settings.data_dir / "llama.pid"
    llama = LlamaProcess(settings.llama_binary, settings.ai_model_file, pid_file, _CONTEXT_TOKENS)
    # Never send questions or passages through a proxy set in the environment.
    http_async_client = httpx.AsyncClient(trust_env=False, timeout=None)  # noqa: S113 - an answer can take minutes
    http_client = httpx.Client(trust_env=False, timeout=None)  # noqa: S113 - same, though unused today

    async def chat_model() -> BaseChatModel:
        return ChatOpenAI(
            base_url=f"{await llama.ensure_started()}/v1",
            api_key=SecretStr(llama.api_key),
            model=settings.ai_model_file.stem,
            temperature=_TEMPERATURE,
            max_completion_tokens=_MAX_ANSWER_TOKENS,
            http_async_client=http_async_client,
            http_client=http_client,
            max_retries=0,  # A dead local server won't come back in a second.
        )

    services = Services(
        ingest=IngestDocument(PdfReader(), embedder, store),
        answerer=GraphAnswerer(embedder, store, chat_model),
        store=store,
        on_shutdown=llama.stop,
    )
    app = create_app(services, token, safe_errors=(LocalAiUnavailableError,))
    app.state.stop_children = llama.stop
    return app
