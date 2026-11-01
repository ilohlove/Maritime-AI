import os
from dataclasses import dataclass, field
from pathlib import Path


def default_database_url() -> str:
    directory = Path(os.environ.get("MARITIME_DATA_DIR", Path.home() / ".maritime-ai"))
    directory.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(directory / 'maritime.db').as_posix()}"


@dataclass(frozen=True)
class Settings:
    model_path: str = field(default_factory=lambda: os.environ.get("MARITIME_MODEL_PATH", ""))
    llama_server: str = field(default_factory=lambda: os.environ.get("MARITIME_LLAMA_SERVER", "llama-server"))
    inference_timeout: float = field(default_factory=lambda: float(os.environ.get("MARITIME_INFERENCE_TIMEOUT", "180")))
    model_port: int = field(default_factory=lambda: int(os.environ.get("MARITIME_MODEL_PORT", "8081")))
    embedding_model_path: str = field(default_factory=lambda: os.environ.get("MARITIME_EMBEDDING_MODEL_PATH", ""))
    embedding_port: int = field(default_factory=lambda: int(os.environ.get("MARITIME_EMBEDDING_PORT", "8082")))
    embedding_timeout: float = field(default_factory=lambda: float(os.environ.get("MARITIME_EMBEDDING_TIMEOUT", "60")))
    semantic_min_score: float = field(default_factory=lambda: float(os.environ.get("MARITIME_SEMANTIC_MIN_SCORE", "0.5")))
    documents_dir: Path | None = None

    database_url: str = field(
        default_factory=lambda: (
            os.environ.get("MARITIME_DATABASE_URL") or default_database_url()
        )
    )
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.environ.get(
                "MARITIME_ALLOWED_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173",
            ).split(",")
            if origin.strip()
        )
    )

    def __post_init__(self):
        if not 1024 <= self.embedding_port <= 65535 or self.embedding_port == self.model_port:
            raise ValueError("Embedding port must be 1024–65535 and distinct from LLM port")
        if not 0 < self.embedding_timeout <= 300:
            raise ValueError("Embedding timeout must be >0 and <=300 seconds")
        if not 0 <= self.semantic_min_score <= 1:
            raise ValueError("Semantic minimum score must be between 0 and 1")
        if not 0 < self.inference_timeout <= 600:
            raise ValueError("MARITIME_INFERENCE_TIMEOUT must be > 0 and <= 600 seconds")
        if not 1024 <= self.model_port <= 65535:
            raise ValueError("MARITIME_MODEL_PORT must be between 1024 and 65535")
