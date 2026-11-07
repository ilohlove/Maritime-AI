import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


def env_flag(name: str) -> bool:
    value = os.environ.get(name, "false")
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return value == "true"


def default_database_url() -> str:
    if os.environ.get("MARITIME_ONLINE_MVP_MODE") == "true":
        raise ValueError(
            "Online MVP requires MARITIME_DATABASE_URL; no SQLite fallback"
        )
    directory = Path(os.environ.get("MARITIME_DATA_DIR", Path.home() / ".maritime-ai"))
    directory.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(directory / 'maritime.db').as_posix()}"


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        repr=False,
        default_factory=lambda: (
            os.environ.get("MARITIME_DATABASE_URL") or default_database_url()
        ),
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
    https_transport: str = field(
        default_factory=lambda: os.environ.get(
            "MARITIME_HTTPS_TRANSPORT", "trusted-proxy"
        )
    )
    gateway_secret: str = field(
        default_factory=lambda: os.environ.get("MARITIME_GATEWAY_SECRET", ""),
        repr=False,
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

    disposable_test_mode: bool = field(
        default_factory=lambda: (
            os.environ.get("MARITIME_DISPOSABLE_TEST_MODE") == "true"
        )
    )
    disposable_ack: str = field(
        default_factory=lambda: os.environ.get("MARITIME_DISPOSABLE_ACK", "")
    )
    disposable_root: str | None = field(
        default_factory=lambda: os.environ.get("MARITIME_DISPOSABLE_ROOT")
    )

    online_mvp_mode: bool = field(
        default_factory=lambda: env_flag("MARITIME_ONLINE_MVP_MODE")
    )
    storage_backend: str = field(
        default_factory=lambda: os.environ.get("MARITIME_STORAGE_BACKEND", "local")
    )
    s3_endpoint: str = field(
        default_factory=lambda: os.environ.get("MARITIME_S3_ENDPOINT", "")
    )
    s3_region: str = field(
        default_factory=lambda: os.environ.get("MARITIME_S3_REGION", "")
    )
    s3_bucket: str = field(
        default_factory=lambda: os.environ.get("MARITIME_S3_BUCKET", "")
    )
    s3_access_key: str = field(
        default_factory=lambda: os.environ.get("MARITIME_S3_ACCESS_KEY", ""), repr=False
    )
    s3_secret_key: str = field(
        default_factory=lambda: os.environ.get("MARITIME_S3_SECRET_KEY", ""), repr=False
    )
    s3_private_bucket: bool = field(
        default_factory=lambda: env_flag("MARITIME_S3_PRIVATE_BUCKET")
    )
    ai_enabled: bool = field(default_factory=lambda: env_flag("MARITIME_AI_ENABLED"))
    ai_input_usd_per_million: str = field(
        default_factory=lambda: os.environ.get(
            "MARITIME_AI_INPUT_USD_PER_MILLION", "0.40"
        )
    )
    ai_output_usd_per_million: str = field(
        default_factory=lambda: os.environ.get(
            "MARITIME_AI_OUTPUT_USD_PER_MILLION", "1.60"
        )
    )
    upload_rate_limit: int = field(
        default_factory=lambda: int(os.environ.get("MARITIME_UPLOAD_RATE_LIMIT", "3"))
    )
    max_documents: int = field(
        default_factory=lambda: int(os.environ.get("MARITIME_MAX_DOCUMENTS", "20"))
    )

    @property
    def mode(self):
        return (
            "online-mvp"
            if self.online_mvp_mode
            else "disposable-synthetic"
            if self.disposable_test_mode
            else "offline-local"
        )

    @property
    def upload_bytes(self):
        return 3_000_000 if self.online_mvp_mode else 10_000_000

    @property
    def upload_request_bytes(self):
        return 4_100_000 if self.online_mvp_mode else 14_100_000

    def __post_init__(self):
        from decimal import Decimal, InvalidOperation

        for price in (self.ai_input_usd_per_million, self.ai_output_usd_per_million):
            try:
                value = Decimal(price)
                if not value.is_finite() or not 0 < value <= 1000:
                    raise ValueError("Invalid model price")
            except (InvalidOperation, ValueError):
                raise ValueError(
                    "Model token prices must be positive finite USD per million"
                ) from None
        if not 1 <= self.upload_rate_limit <= 20 or not 1 <= self.max_documents <= 20:
            raise ValueError("Invalid upload rate or document count limit")
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("MARITIME_STORAGE_BACKEND must be local or s3")
        if self.storage_backend == "s3":
            endpoint = urlparse(self.s3_endpoint)
            if (
                endpoint.scheme != "https"
                or not endpoint.hostname
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
                or not self.s3_region
                or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.s3_bucket)
                or not self.s3_access_key
                or not self.s3_secret_key
                or not self.s3_private_bucket
            ):
                raise ValueError(
                    "S3 requires an HTTPS endpoint, region, bucket, credentials and private bucket acknowledgement"
                )
        if self.online_mvp_mode:
            from sqlalchemy.engine import make_url
            from app.db.session import database_url

            db = make_url(database_url(self.database_url))
            if (
                self.disposable_test_mode
                or self.environment != "production"
                or self.https_transport != "signed-gateway"
                or self.auth_transport != "bearer"
                or db.get_backend_name() != "postgresql"
                or not db.host
                or not db.database
                or db.query.get("sslmode") != "verify-full"
                or self.storage_backend != "s3"
                or not self.storage_persistent
            ):
                raise ValueError(
                    "Online MVP requires production, signed-gateway, bearer auth, verify-full TLS PostgreSQL and persistent private S3; no ephemeral fallback"
                )
            if len(self.openai_models) != 1:
                raise ValueError(
                    "Online MVP requires one model with explicitly configured token pricing"
                )
            if self.ai_enabled and (
                not self.openai_api_key
                or self.openai_api_key == "DISABLED-DISPOSABLE-TEST"
            ):
                raise ValueError(
                    "Enabled online inference requires a backend OpenAI key"
                )
        elif self.storage_backend != "local":
            raise ValueError("S3 storage requires explicit online MVP mode")

        if self.https_transport not in {"trusted-proxy", "signed-gateway"}:
            raise ValueError("Invalid MARITIME_HTTPS_TRANSPORT")
        if self.https_transport == "signed-gateway":
            if (
                self.environment != "production"
                or not (self.disposable_test_mode or self.online_mvp_mode)
                or not re.fullmatch(r"[0-9a-f]{64}", self.gateway_secret)
                or os.environ.get("MARITIME_TRUSTED_PROXY_IPS", "").strip()
            ):
                raise ValueError(
                    "Signed gateway requires production disposable or online mode, a 64-character "
                    "lowercase hex MARITIME_GATEWAY_SECRET and no trusted proxy IPs"
                )
        elif self.gateway_secret:
            raise ValueError(
                "MARITIME_GATEWAY_SECRET requires signed-gateway transport"
            )
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
        if self.disposable_test_mode:
            from app.core.disposable import validate_disposable

            validate_disposable(self)
        elif self.disposable_ack or self.disposable_root:
            raise ValueError(
                "Disposable settings require explicit MARITIME_DISPOSABLE_TEST_MODE=true"
            )
        if self.environment == "production":
            if not self.password_hash or (
                not self.online_mvp_mode and not self.openai_api_key
            ):
                raise ValueError(
                    "Production requires MARITIME_PASSWORD_HASH and OPENAI_API_KEY"
                )
            if not self.online_mvp_mode and (
                not self.documents_dir
                or (not self.storage_persistent and not self.disposable_test_mode)
            ):
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
