import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.main import create_app
from app.services.auth import hash_password
from fastapi.testclient import TestClient


def migrate(app):
    config = Config("alembic.ini")
    with app.state.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


TEST_PASSWORD = "synthetic-private-test-password"
TEST_HASH = hash_password(TEST_PASSWORD)


def sign_in(client):
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return response.json()


@pytest.fixture
def configured_app(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        password_hash=TEST_HASH,
        ai_rate_limit=100,
        ai_daily_token_budget=10000000,
    )
    app = create_app(settings)
    migrate(app)
    return app, settings


@pytest.fixture
def client(configured_app):
    with TestClient(configured_app[0]) as client:
        sign_in(client)
        yield client
