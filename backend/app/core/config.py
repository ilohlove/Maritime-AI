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
        if not 0 < self.inference_timeout <= 600:
            raise ValueError("MARITIME_INFERENCE_TIMEOUT must be > 0 and <= 600 seconds")
        if not 1024 <= self.model_port <= 65535:
            raise ValueError("MARITIME_MODEL_PORT must be between 1024 and 65535")
