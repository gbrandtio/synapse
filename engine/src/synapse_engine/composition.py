"""Wire the real adapters to the use cases."""

from __future__ import annotations

from fastapi import FastAPI
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from synapse_engine.adapters.ai.ask_graph import GraphAnswerer
from synapse_engine.adapters.ai.embedder import FastEmbedEmbedder
from synapse_engine.adapters.ai.ollama_process import OllamaProcess, OllamaUnavailableError
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
    pid_file = settings.data_dir / "ollama.pid"
    ollama = OllamaProcess(settings.ollama_binary, settings.ollama_models, pid_file)

    async def chat_model() -> BaseChatModel:
        return ChatOllama(
            base_url=await ollama.ensure_started(),
            model=settings.ai_model,
            temperature=_TEMPERATURE,
            num_predict=_MAX_ANSWER_TOKENS,
            reasoning=False,
            num_ctx=_CONTEXT_TOKENS,
            # Never send questions or passages through a proxy set in the environment.
            client_kwargs={"trust_env": False},
        )

    services = Services(
        ingest=IngestDocument(PdfReader(), embedder, store),
        answerer=GraphAnswerer(embedder, store, chat_model),
        store=store,
        on_shutdown=ollama.stop,
    )
    app = create_app(services, token, safe_errors=(OllamaUnavailableError,))
    app.state.stop_children = ollama.stop
    return app
