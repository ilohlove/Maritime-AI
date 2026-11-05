"""Explicit synthetic-only, no-inference profile for disposable hosting tests."""

import tempfile
from pathlib import Path

DISPOSABLE_ACK = "SYNTHETIC_ONLY_DATA_LOSS_NO_PAID_AI"
DISABLED_API_KEY = "DISABLED-DISPOSABLE-TEST"
STORAGE_WARNING = (
    "DISPOSABLE SYNTHETIC TEST: database, documents, sessions and rate/quota state "
    "may be lost on restart, sleep or redeploy. Real AI is disabled. "
    "Only the bundled synthetic document can be imported; vessel writes are disabled."
)
SYNTHETIC_DOCUMENT = {
    "title": "SYNTHETIC TRAINING SAMPLE — NOT MARITIME ADVICE",
    "format": "text",
    "content": "SYNTHETIC TRAINING ONLY. This is fictional test data, not a regulation.\nIn this fictional exercise, the imaginary lifeboat inspection occurs weekly.\nNo real vessel, person or operational instruction is described.\n",
}


def validate_disposable(settings):
    if (
        settings.environment != "production"
        or settings.disposable_ack != DISPOSABLE_ACK
    ):
        raise ValueError(
            "Disposable testing requires production security and explicit synthetic/data-loss/no-paid-AI acknowledgement"
        )
    if settings.storage_persistent or settings.auth_transport != "bearer":
        raise ValueError(
            "Disposable mode cannot claim persistent storage and requires bearer sessions"
        )
    if settings.openai_api_key != DISABLED_API_KEY:
        raise ValueError(
            "Disposable mode forbids real API keys; use the documented disabled placeholder"
        )
    if not settings.disposable_root:
        raise ValueError(
            "Use scripts/start_disposable_test.py to create isolated temporary storage"
        )
    root = Path(settings.disposable_root)
    if (
        not root.is_absolute()
        or root.is_symlink()
        or not root.is_dir()
        or not root.name.startswith("maritime-disposable-")
        or not root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    ):
        raise ValueError("Disposable storage must be an isolated temporary directory")
    from sqlalchemy.engine import make_url

    database = make_url(settings.database_url).database
    if (
        not database
        or Path(database).resolve() != root.resolve() / "maritime.db"
        or not settings.documents_dir
        or Path(settings.documents_dir).resolve() != root.resolve() / "originals"
    ):
        raise ValueError(
            "Disposable database and originals must stay inside their isolated temporary root"
        )
