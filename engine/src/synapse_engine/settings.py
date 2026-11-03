"""Where the engine finds its data and bundled parts. The app sets these when it starts us."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BUNDLED_MODEL_FILE = "gemma-3-1b-Q4_K_M.gguf"


@dataclass(frozen=True, slots=True)
class Settings:
    """Paths and names the engine needs."""

    data_dir: Path
    embedding_dir: Path
    llama_binary: Path
    ai_model_file: Path

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
            llama_binary=Path(os.environ.get("SYNAPSE_LLAMA_BIN", data / "llama/llama-server")),
            ai_model_file=Path(
                os.environ.get("SYNAPSE_AI_MODEL_FILE", data / "models/ai" / BUNDLED_MODEL_FILE)
            ),
        )
