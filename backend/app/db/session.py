from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def create_database(url: str):
    if not url.startswith("sqlite:"):
        raise ValueError("Task 01 supports local SQLite databases only")
    engine = create_engine(
        url, connect_args={"check_same_thread": False, "timeout": 10}
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")

    return engine, sessionmaker(engine, expire_on_commit=False)
