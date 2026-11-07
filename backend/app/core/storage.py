"""Validate migration state and writable persistent volume configuration."""

import logging
import tempfile
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


def document_directory(settings) -> Path | None:
    if settings.storage_backend == "s3":
        return None
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


def validate_storage(engine, settings, directory, storage=None):
    try:
        with engine.connect() as connection:
            if (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                != "0004"
            ):
                raise RuntimeError(
                    "Database migrations are required; run alembic upgrade head before startup"
                )
            if engine.dialect.name == "sqlite":
                connection.execute(text("SELECT rowid FROM document_fts LIMIT 1"))
            else:
                connection.execute(
                    text("SELECT search_vector FROM document_chunks LIMIT 1")
                )
            connection.execute(text("SELECT digest FROM auth_sessions LIMIT 1"))
            rows = connection.execute(
                text(
                    "SELECT original_path, byte_size FROM documents WHERE original_path IS NOT NULL AND state='ready'"
                )
            ).all()
            if settings.online_mvp_mode:
                legacy = connection.execute(
                    text(
                        "SELECT count(*) FROM documents WHERE owner_id IS NULL OR original_path IS NULL"
                    )
                ).scalar()
                legacy += connection.execute(
                    text("SELECT count(*) FROM vessels WHERE owner_id IS NULL")
                ).scalar()
                if legacy:
                    raise RuntimeError(
                        "Online storage contains unowned/legacy data; perform an audited import into a fresh database"
                    )
        if storage is not None:
            storage.validate()
        for name, expected in rows:
            try:
                from app.core.object_storage import valid_key

                valid_key(name)
                if storage is not None:
                    size = storage.size(name)
                else:
                    original = directory / name
                    if original.is_symlink():
                        raise ValueError
                    size = original.stat().st_size
                if size <= 0 or (expected is not None and size != expected):
                    raise ValueError
            except Exception:
                raise RuntimeError(
                    "A referenced original document is missing or invalid. Restore the correct persistent document storage."
                ) from None
    except SQLAlchemyError:
        raise RuntimeError(
            "Cannot validate storage/schema. Check volume access and run alembic upgrade head before startup."
        ) from None
    for path in (
        ()
        if directory is None
        else (Path(make_url(settings.database_url).database).parent, directory)
    ):
        with tempfile.TemporaryFile(dir=path):
            pass
    if settings.disposable_test_mode:
        from app.core.disposable import STORAGE_WARNING

        logging.getLogger("maritime.storage").warning(STORAGE_WARNING)
    elif not settings.storage_persistent:
        logging.getLogger("maritime.storage").warning(
            "STORAGE NOT CONFIRMED PERSISTENT: SQLite and document originals may be lost on host restart/redeployment. Do not use operational data."
        )
