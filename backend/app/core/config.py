import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


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

    environment: str = field(
        default_factory=lambda: os.environ.get("MARITIME_ENV", "development")
    )
    admin_username: str = field(
        default_factory=lambda: os.environ.get("MARITIME_ADMIN_USERNAME", "admin")
    )
    password_hash: str = field(
        default_factory=lambda: os.environ.get("MARITIME_PASSWORD_HASH", ""), repr=False
    )
    auth_transport: str = field(
        default_factory=lambda: os.environ.get("MARITIME_AUTH_TRANSPORT", "bearer")
    )
    session_seconds: int = field(
        default_factory=lambda: int(os.environ.get("MARITIME_SESSION_SECONDS", "3600"))
    )
    trusted_hosts: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            h.strip()
            for h in os.environ.get(
                "MARITIME_TRUSTED_HOSTS", "127.0.0.1,localhost,testserver"
            ).split(",")
            if h.strip()
        )
    )
    documents_dir: str | None = field(
        default_factory=lambda: os.environ.get("MARITIME_DOCUMENTS_DIR")
    )
    storage_persistent: bool = field(
        default_factory=lambda: os.environ.get("MARITIME_STORAGE_PERSISTENT") == "true"
    )
    login_limit: int = field(
        default_factory=lambda: int(os.environ.get("MARITIME_LOGIN_LIMIT", "5"))
    )
    ai_rate_limit: int = field(
        default_factory=lambda: int(os.environ.get("MARITIME_AI_RATE_LIMIT", "5"))
    )
    ai_concurrency: int = field(
        default_factory=lambda: int(os.environ.get("MARITIME_AI_CONCURRENCY", "1"))
    )
    ai_daily_token_budget: int = field(
        default_factory=lambda: int(
            os.environ.get("MARITIME_AI_DAILY_TOKEN_BUDGET", "100000")
        )
    )
    ai_max_input_tokens: int = field(
        default_factory=lambda: int(
            os.environ.get("MARITIME_AI_MAX_INPUT_TOKENS", "20000")
        )
    )
    ai_output_tokens: int = field(
        default_factory=lambda: int(os.environ.get("MARITIME_AI_OUTPUT_TOKENS", "2000"))
    )
    ai_translation_tokens: int = field(
        default_factory=lambda: int(
            os.environ.get("MARITIME_AI_TRANSLATION_TOKENS", "512")
        )
    )

    def __post_init__(self):
        if self.environment not in {"development", "production"}:
            raise ValueError("MARITIME_ENV must be development or production")
        if self.auth_transport not in {"bearer", "cookie"}:
            raise ValueError("MARITIME_AUTH_TRANSPORT must be bearer or cookie")
        if not 300 <= self.session_seconds <= 86400:
            raise ValueError("Session duration must be 300–86400 seconds")
        if not self.admin_username or len(self.admin_username) > 100:
            raise ValueError("Invalid administrator username")
        if not 0 < self.openai_timeout <= 120:
            raise ValueError("OPENAI_TIMEOUT_SECONDS must be > 0 and <= 120")
        if self.openai_max_retries != 0:
            raise ValueError(
                "OPENAI_MAX_RETRIES must be 0: automatic paid retries are disabled"
            )
        if (
            self.openai_model not in self.openai_models
            or not self.openai_models
            or any(not m or len(m) > 100 for m in self.openai_models)
        ):
            raise ValueError(
                "OPENAI_MODEL must be included in a nonempty OPENAI_MODELS allowlist"
            )
        for value, limit in (
            (self.login_limit, 100),
            (self.ai_rate_limit, 100),
            (self.ai_concurrency, 8),
            (self.ai_daily_token_budget, 100000000),
            (self.ai_max_input_tokens, 100000),
            (self.ai_output_tokens, 8000),
            (self.ai_translation_tokens, 2000),
        ):
            if not 1 <= value <= limit:
                raise ValueError("Invalid rate, concurrency, token limit or budget")
        if not self.trusted_hosts or any(
            "*" in h or "/" in h or ":" in h for h in self.trusted_hosts
        ):
            raise ValueError(
                "Use explicit trusted hostnames without wildcards or ports"
            )
        for origin in self.allowed_origins:
            parsed = urlparse(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise ValueError(
                    "CORS origins must be explicit HTTP(S) origins without paths"
                )
        if not self.allowed_origins:
            raise ValueError("An explicit frontend CORS origin is required")
        if self.password_hash:
            from app.services.auth import validate_password_hash

            validate_password_hash(self.password_hash)
        if self.environment == "production":
            if not self.password_hash or not self.openai_api_key:
                raise ValueError(
                    "Production requires MARITIME_PASSWORD_HASH and OPENAI_API_KEY"
                )
            if not self.storage_persistent or not self.documents_dir:
                raise ValueError(
                    "Production requires persistent storage acknowledgement and MARITIME_DOCUMENTS_DIR"
                )
            if any(urlparse(o).scheme != "https" for o in self.allowed_origins):
                raise ValueError("Production CORS origins must use HTTPS")
            if any(
                h in {"localhost", "127.0.0.1", "testserver"}
                for h in self.trusted_hosts
            ):
                raise ValueError("Production requires explicit backend domain names")
            if os.environ.get("WEB_CONCURRENCY", "1") != "1":
                raise ValueError("This MVP supports exactly one backend worker/replica")
            if self.auth_transport == "cookie" and any(
                urlparse(o).hostname not in self.trusted_hosts
                for o in self.allowed_origins
            ):
                raise ValueError(
                    "Cookie mode requires same-origin frontend hosting; use bearer for GitHub Pages"
                )
