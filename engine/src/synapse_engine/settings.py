"""Where the engine finds its data and bundled parts. The app sets these when it starts us."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BUNDLED_MODEL = "gemma3:1b"


@dataclass(frozen=True, slots=True)
class Settings:
    """Paths and names the engine needs."""

    data_dir: Path
    embedding_dir: Path
    ollama_binary: Path
    ollama_models: Path
    ai_model: str = BUNDLED_MODEL

    @property
    def database(self) -> Path:
        """Return the path of the single SQLite file."""
        return self.data_dir / "synapse.db"

    @classmethod
    def from_environment(cls) -> Settings:
        """Read settings from the environment, with paths inside the data folder by default."""
        data = Path(os.environ.get("SYNAPSE_DATA_DIR", Path.home() / ".synapse"))
        return cls(
            data_dir=data,
            embedding_dir=Path(os.environ.get("SYNAPSE_EMBEDDING_DIR", data / "models/embedding")),
            ollama_binary=Path(os.environ.get("SYNAPSE_OLLAMA_BIN", data / "ollama/ollama")),
            ollama_models=Path(os.environ.get("SYNAPSE_OLLAMA_MODELS", data / "models/ollama")),
            ai_model=os.environ.get("SYNAPSE_AI_MODEL", BUNDLED_MODEL),
        )
