import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


def migrate(app):
    config = Config("alembic.ini")
    with app.state.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


@pytest.fixture
def configured_app(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")
    app = create_app(settings)
    migrate(app)
    return app, settings


@pytest.fixture
def client(configured_app):
    with TestClient(configured_app[0]) as client:
        yield client
