"""Dialect-aware engines; schema changes are always explicit Alembic operations."""

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url(value: str) -> str:
    # Use one installed synchronous driver for direct and Supabase pooler URLs.
    if value.startswith(("postgres://", "postgresql://")):
        value = "postgresql+psycopg://" + value.split("://", 1)[1]
    if make_url(value).drivername not in {"sqlite", "postgresql+psycopg"}:
        raise ValueError("Use SQLite or PostgreSQL with psycopg")
    return value


def create_database(url: str):
    url = database_url(url)
    if make_url(url).get_backend_name() == "sqlite":
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 10},
            hide_parameters=True,
        )

        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=10000")
    else:
        engine = create_engine(
            url,
            pool_size=2,
            max_overflow=0,
            pool_timeout=5,
            pool_recycle=300,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": 5, "prepare_threshold": None},
        )

        @event.listens_for(engine, "connect")
        def configure_postgres(connection, _):
            # SET at connection creation works through a session pooler. For a
            # transaction pooler, configure role-level timeouts as documented.
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = '10000'")
                cursor.execute("SET lock_timeout = '5000'")
            connection.commit()

    return engine, sessionmaker(engine, expire_on_commit=False)


@contextmanager
def security_transaction(engine):
    """Serialize SQLite writers; PG upserts/conditional updates take row locks."""
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
