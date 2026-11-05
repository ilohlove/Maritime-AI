import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.core.config import Settings
from app.core.disposable import (
    DISABLED_API_KEY,
    DISPOSABLE_ACK,
    STORAGE_WARNING,
    SYNTHETIC_DOCUMENT,
)
from app.main import create_app
from app.services.document_ai import ProviderRegistration, WorkflowError
from app.services.openai_provider import OpenAIProvider
from conftest import TEST_HASH, TEST_PASSWORD, migrate
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture
def disposable_settings():
    with tempfile.TemporaryDirectory(prefix="maritime-disposable-") as directory:
        root = Path(directory)
        yield Settings(
            environment="production",
            password_hash=TEST_HASH,
            openai_api_key=DISABLED_API_KEY,
            database_url=f"sqlite:///{root / 'maritime.db'}",
            documents_dir=str(root / "originals"),
            trusted_hosts=("api.example.invalid",),
            allowed_origins=("https://ilohlove.github.io",),
            storage_persistent=False,
            disposable_test_mode=True,
            disposable_ack=DISPOSABLE_ACK,
            disposable_root=directory,
        )


def login(client):
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    assert response.json()["storage_warning"] == STORAGE_WARNING
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]


@pytest.mark.parametrize(
    "changes",
    [
        {"disposable_ack": ""},
        {"environment": "development"},
        {"password_hash": ""},
        {"openai_api_key": ""},
        {"openai_api_key": "synthetic-looking-live-key"},
        {"storage_persistent": True},
        {"auth_transport": "cookie"},
        {"documents_dir": "/tmp/unrelated"},
        {"database_url": "sqlite:////tmp/unrelated.db"},
        {"disposable_root": "/tmp"},
        {"allowed_origins": ("http://localhost",)},
        {"trusted_hosts": ("*",)},
        {"openai_max_retries": 1},
    ],
)
def test_disposable_cannot_disable_production_controls(disposable_settings, changes):
    with pytest.raises(ValueError):
        replace(disposable_settings, **changes)


def test_normal_production_still_rejects_ephemeral_storage(disposable_settings):
    with pytest.raises(ValueError):
        replace(
            disposable_settings,
            disposable_test_mode=False,
            disposable_ack="",
            disposable_root=None,
        )


def test_disposable_preserves_auth_tls_cors_and_explicit_warning(
    disposable_settings, caplog
):
    app = create_app(disposable_settings)
    migrate(app)
    with TestClient(app, base_url="https://api.example.invalid") as client:
        assert client.get("/api/documents").status_code == 401
        assert client.get("http://api.example.invalid/api/health").status_code == 400
        assert (
            client.get("/api/health", headers={"Host": "evil.invalid"}).status_code
            == 400
        )
        assert (
            client.post(
                "/api/auth/login",
                json={"username": "admin", "password": TEST_PASSWORD},
                headers={"Origin": "https://evil.invalid"},
            ).status_code
            == 403
        )
        login(client)
        configuration = client.get("/api/ai/providers").json()
        assert configuration["disposable_test_mode"] is True
        assert configuration["providers"][0]["configured"] is False
        assert configuration["providers"][0]["status"] == "disabled_disposable"
        assert DISABLED_API_KEY not in str(configuration)
        assert (
            client.post("/api/vessels", json={"vessel_name": "SYNTHETIC"}).status_code
            == 403
        )
        assert client.post("/api/auth/logout", json={}).status_code == 200
        assert client.get("/api/documents").status_code == 401
    assert STORAGE_WARNING in caplog.text


def test_only_exact_fixture_can_be_stored_and_no_provider_can_be_called(
    disposable_settings,
):
    app = create_app(disposable_settings)
    migrate(app)
    factory = Mock()
    app.state.document_providers["openai"] = ProviderRegistration(True, factory)
    with TestClient(app, base_url="https://api.example.invalid") as client:
        login(client)
        for changes in (
            {"content": "SYNTHETIC label on arbitrary real text"},
            {"title": "private filename"},
            {"format": "pdf"},
        ):
            response = client.post("/api/documents", json=SYNTHETIC_DOCUMENT | changes)
            assert response.status_code == 422
        assert client.get("/api/documents").json() == []
        imported = client.post("/api/documents", json=SYNTHETIC_DOCUMENT)
        assert imported.status_code == 201, imported.text
        identifier = imported.json()["id"]
        assert (
            app.state.document_directory / (identifier + ".bin")
        ).read_text() == SYNTHETIC_DOCUMENT["content"]
        response = client.post(
            f"/api/documents/{identifier}/questions",
            json={
                "question": "When is the fictional inspection?",
                "model": "gpt-4.1-mini",
                "external_consent": True,
            },
        )
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "disposable_ai_disabled"
        factory.assert_not_called()
        with app.state.engine.connect() as connection:
            assert (
                connection.execute(text("SELECT count(*) FROM ai_daily_usage")).scalar()
                == 0
            )
    with pytest.raises(WorkflowError) as error:
        OpenAIProvider(disposable_settings, "gpt-4.1-mini")
    assert error.value.code == "disposable_ai_disabled"


def test_disposable_still_requires_migrations(disposable_settings):
    with (
        pytest.raises(RuntimeError, match="storage/schema"),
        TestClient(
            create_app(disposable_settings), base_url="https://api.example.invalid"
        ),
    ):
        pass


def test_disposable_still_rejects_missing_originals(disposable_settings):
    app = create_app(disposable_settings)
    migrate(app)
    with TestClient(app, base_url="https://api.example.invalid") as client:
        login(client)
        imported = client.post("/api/documents", json=SYNTHETIC_DOCUMENT).json()
    (app.state.document_directory / (imported["id"] + ".bin")).unlink()
    with (
        pytest.raises(RuntimeError, match="original document is missing"),
        TestClient(
            create_app(disposable_settings), base_url="https://api.example.invalid"
        ),
    ):
        pass
