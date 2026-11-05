"""Validate migration state and writable persistent volume configuration."""

import logging
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


def document_directory(settings) -> Path:
    database = make_url(settings.database_url).database
    if not database or database == ":memory:" or not Path(database).is_absolute():
        raise ValueError("Use an absolute SQLite database file path")
    directory = (
        Path(settings.documents_dir)
        if settings.documents_dir
        else Path(database).parent / "documents"
    )
    if not directory.is_absolute():
        raise ValueError("MARITIME_DOCUMENTS_DIR must be an absolute path")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory.resolve()


def validate_storage(engine, settings, directory):
    try:
        with engine.connect() as connection:
            if (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                != "0003"
            ):
                raise RuntimeError(
                    "Database migrations are required; run alembic upgrade head before startup"
                )
            connection.execute(text("SELECT rowid FROM document_fts LIMIT 1"))
            connection.execute(text("SELECT digest FROM auth_sessions LIMIT 1"))
            for name in connection.execute(
                text(
                    "SELECT original_path FROM documents WHERE original_path IS NOT NULL"
                )
            ).scalars():
                try:
                    if Path(name).name != name or not name.endswith(".bin"):
                        raise ValueError
                    UUID(name[:-4])
                    original = directory / name
                    if (
                        original.is_symlink()
                        or not original.is_file()
                        or original.stat().st_size == 0
                    ):
                        raise ValueError
                except (ValueError, OSError):
                    raise RuntimeError(
                        "A referenced original document is missing or invalid. Restore the correct persistent document volume."
                    ) from None
    except SQLAlchemyError:
        raise RuntimeError(
            "Cannot validate storage/schema. Check volume access and run alembic upgrade head before startup."
        ) from None
    for path in (Path(make_url(settings.database_url).database).parent, directory):
        with tempfile.TemporaryFile(dir=path):
            pass
    if settings.disposable_test_mode:
        from app.core.disposable import STORAGE_WARNING

        logging.getLogger("maritime.storage").warning(STORAGE_WARNING)
    elif not settings.storage_persistent:
        logging.getLogger("maritime.storage").warning(
            "STORAGE NOT CONFIRMED PERSISTENT: SQLite and document originals may be lost on host restart/redeployment. Do not use operational data."
        )
