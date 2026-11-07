from alembic import context
from app.core.config import Settings
from app.db.session import Base, database_url
from app.models.document import Document, DocumentChunk  # noqa: F401
from app.models.security import AuthSession, DailyUsage, RateWindow  # noqa: F401
from app.models.vessel import Vessel  # noqa: F401 - register ORM metadata for autogeneration
from sqlalchemy import create_engine, pool


def include_object(obj, name, type_, reflected, compare_to):
    # The PG generated search column/GIN index and SQLite virtual FTS tables
    # are migration-owned. Keep dialect-specific internals out of ORM diffs.
    if reflected and compare_to is None:
        if (
            type_ == "column"
            and obj.table.name == "document_chunks"
            and name == "search_vector"
        ):
            return False
        if type_ == "index" and name == "ix_chunks_search":
            return False
        if type_ == "table" and name.startswith("document_fts"):
            return False
    return True


config = context.config
# Tests may provide a specific connection; otherwise use the same runtime settings.
connection = config.attributes.get("connection")
if context.is_offline_mode():
    context.configure(
        url=database_url(Settings().database_url),
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = None
    if connection is None:
        engine = create_engine(
            database_url(Settings().database_url), poolclass=pool.NullPool
        )
        connection = engine.connect()
    try:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            render_as_batch=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if engine is not None:
            connection.close()
            engine.dispose()
