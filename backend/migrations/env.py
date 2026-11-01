from alembic import context
from app.core.config import Settings
from app.db.session import Base
from app.models.vessel import Vessel  # noqa: F401 - register ORM metadata for autogeneration
from sqlalchemy import create_engine, pool

config = context.config
# Tests may provide a specific connection; otherwise use the same runtime settings.
connection = config.attributes.get("connection")
if context.is_offline_mode():
    context.configure(
        url=Settings().database_url, target_metadata=Base.metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = None
    if connection is None:
        engine = create_engine(Settings().database_url, poolclass=pool.NullPool)
        connection = engine.connect()
    try:
        context.configure(
            connection=connection, target_metadata=Base.metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if engine is not None:
            connection.close()
            engine.dispose()
