import os
from dataclasses import dataclass, field
from pathlib import Path


def default_database_url() -> str:
    directory = Path(os.environ.get("MARITIME_DATA_DIR", Path.home() / ".maritime-ai"))
    directory.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(directory / 'maritime.db').as_posix()}"


@dataclass(frozen=True)
class Settings:
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
    openai_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""), repr=False
    )
    openai_model: str = field(
        default_factory=lambda: os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    )
    openai_models: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            m.strip()
            for m in os.environ.get(
                "OPENAI_MODELS", os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
            ).split(",")
            if m.strip()
        )
    )
    openai_timeout: float = field(
        default_factory=lambda: float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30"))
    )
    openai_max_retries: int = field(
        default_factory=lambda: int(os.environ.get("OPENAI_MAX_RETRIES", "0"))
    )

    def __post_init__(self):
        if not 0 < self.openai_timeout <= 120:
            raise ValueError("OPENAI_TIMEOUT_SECONDS must be > 0 and <= 120")
        if not 0 <= self.openai_max_retries <= 2:
            raise ValueError("OPENAI_MAX_RETRIES must be between 0 and 2")
        if self.openai_model not in self.openai_models:
            raise ValueError("OPENAI_MODEL must be included in OPENAI_MODELS")
