import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from app.core.config import Settings
from app.main import create_app
from app.services.auth import digest
from app.services.document_ai import WorkflowError
from conftest import TEST_HASH, TEST_PASSWORD, migrate, sign_in
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture
def frozen_rate_clock(monkeypatch):
    # Window-boundary timing must not make throttling/restart checks flaky.
    from types import SimpleNamespace

    import app.services.auth as authentication

    now = time.time()
    monkeypatch.setattr(authentication, "time", SimpleNamespace(time=lambda: now))


def build(tmp_path, **changes):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'security.db'}",
        password_hash=TEST_HASH,
        **changes,
    )
    app = create_app(settings)
    migrate(app)
    return app, settings


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/vessels"),
        ("POST", "/api/vessels"),
        ("PATCH", "/api/vessels/00000000-0000-0000-0000-000000000000"),
        ("GET", "/api/documents"),
        ("POST", "/api/documents"),
        ("GET", "/api/ai/providers"),
        ("POST", "/api/documents/00000000-0000-0000-0000-000000000000/questions"),
        ("GET", "/api/auth/session"),
        ("POST", "/api/auth/logout"),
        ("GET", "/openapi.json"),
        ("GET", "/docs"),
    ],
)
def test_nonpublic_endpoints_deny_anonymous(configured_app, method, path):
    with TestClient(configured_app[0]) as client:
        response = client.request(
            method,
            path,
            headers={"content-type": "application/json"},
            content="{}" if method != "GET" else None,
        )
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
        with configured_app[0].state.engine.connect() as connection:
            assert (
                connection.execute(text("SELECT count(*) FROM ai_daily_usage")).scalar()
                == 0
            )


def test_login_expiry_revocation_and_digests(tmp_path):
    app, _ = build(tmp_path)
    with TestClient(app) as client:
        session = sign_in(client)
        assert (
            "set-cookie"
            not in client.post(
                "/api/auth/login", json={"username": "admin", "password": "wrong"}
            ).headers
        )
        assert client.get("/api/auth/session").json()["user"] == "admin"
        with app.state.engine.connect() as connection:
            row = (
                connection.execute(text("SELECT * FROM auth_sessions")).mappings().one()
            )
            assert row["digest"] == digest(session["access_token"])
            assert session["access_token"] not in str(dict(row))
            assert TEST_PASSWORD not in str(dict(row))
        assert client.post("/api/auth/logout", json={}).status_code == 200
        assert client.get("/api/vessels").status_code == 401
        sign_in(client)
        with app.state.engine.begin() as connection:
            connection.execute(
                text("UPDATE auth_sessions SET expires_at=:past"),
                {"past": time.time() - 1},
            )
        assert (
            client.get("/api/documents").json()["detail"]["code"] == "session_expired"
        )


def test_password_rotation_revokes_existing_sessions(tmp_path):
    from app.services.auth import hash_password

    app, settings = build(tmp_path)
    with TestClient(app) as client:
        token = sign_in(client)["access_token"]
    replacement = create_app(
        replace(settings, password_hash=hash_password("different-synthetic-password"))
    )
    with TestClient(replacement) as client:
        assert (
            client.get(
                "/api/vessels", headers={"Authorization": "Bearer " + token}
            ).status_code
            == 401
        )


def test_login_rate_limit_persists_restart(tmp_path, frozen_rate_clock):
    app, settings = build(tmp_path, login_limit=2)
    with TestClient(app) as client:
        for username in ("admin", "unknown"):
            response = client.post(
                "/api/auth/login", json={"username": username, "password": "wrong"}
            )
            assert response.status_code == 401
            assert response.json()["detail"]["code"] == "invalid_credentials"
    with TestClient(create_app(settings)) as client:
        assert (
            client.post(
                "/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD}
            ).status_code
            == 429
        )


def test_auth_input_sanitization_and_body_limit(configured_app):
    with TestClient(configured_app[0]) as client:
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "SECRET-MARKER" * 100},
        )
        assert response.status_code == 422
        assert "SECRET-MARKER" not in response.text
        assert (
            client.post(
                "/api/auth/login",
                content="x" * 4097,
                headers={"content-type": "application/json"},
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/api/auth/login",
                content="password=test",
                headers={"content-type": "application/x-www-form-urlencoded"},
            ).status_code
            == 415
        )


def test_cookie_flags_csrf_logout_and_cors(tmp_path):
    app, _ = build(
        tmp_path, auth_transport="cookie", allowed_origins=("https://testserver",)
    )
    with TestClient(app, base_url="https://testserver") as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": TEST_PASSWORD},
            headers={"Origin": "https://testserver"},
        )
        assert login.status_code == 200
        assert "access_token" not in login.json()
        cookie = login.headers["set-cookie"]
        assert all(
            flag in cookie
            for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/")
        )
        assert client.get("/api/vessels").status_code == 200
        assert client.post("/api/vessels", json={}).status_code == 403
        assert (
            client.post(
                "/api/vessels",
                json={},
                headers={"Origin": "https://testserver", "X-CSRF-Token": "wrong"},
            ).status_code
            == 403
        )
        headers = {
            "Origin": "https://testserver",
            "X-CSRF-Token": login.json()["csrf_token"],
        }
        assert (
            client.post(
                "/api/vessels",
                json={"vessel_name": "SYNTHETIC COOKIE"},
                headers=headers,
            ).status_code
            == 201
        )
        assert (
            client.post("/api/auth/logout", json={}, headers=headers).status_code == 200
        )
        assert client.get("/api/vessels").status_code == 401


def test_allowed_cors_preflight_and_unauthorized_response(configured_app):
    with TestClient(configured_app[0]) as client:
        origin = "http://127.0.0.1:5173"
        response = client.options(
            "/api/documents",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,Content-Type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"
        denied = client.get("/api/documents", headers={"Origin": origin})
        assert denied.status_code == 401
        assert denied.headers["access-control-allow-origin"] == origin
        evil = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": TEST_PASSWORD},
            headers={"Origin": "https://evil.invalid"},
        )
        assert evil.status_code == 403
        assert "access-control-allow-origin" not in evil.headers


def test_host_header_and_spoofed_proxy_are_not_trusted(configured_app):
    with TestClient(configured_app[0]) as client:
        assert (
            client.get("/api/health", headers={"Host": "evil.invalid"}).status_code
            == 400
        )
        # The app never trusts forwarded headers itself. Uvicorn must whitelist its proxy.
        assert (
            client.get(
                "/api/vessels",
                headers={"X-Forwarded-For": "trusted", "X-Forwarded-Proto": "https"},
            ).status_code
            == 401
        )


def test_production_fail_closed_and_https(tmp_path):
    base = {
        "database_url": f"sqlite:///{tmp_path / 'production.db'}",
        "environment": "production",
        "password_hash": TEST_HASH,
        "openai_api_key": "synthetic-not-live",
        "storage_persistent": True,
        "documents_dir": str(tmp_path / "originals"),
        "allowed_origins": ("https://ilohlove.github.io",),
        "trusted_hosts": ("api.example.invalid",),
    }
    for changes in (
        {"password_hash": ""},
        {"openai_api_key": ""},
        {"storage_persistent": False},
        {"documents_dir": None},
        {"allowed_origins": ("*",)},
        {"trusted_hosts": ("*",)},
        {"allowed_origins": ("http://localhost",)},
        {"auth_transport": "cookie"},
        {"openai_max_retries": 1},
    ):
        with pytest.raises(ValueError):
            Settings(**(base | changes))
    settings = Settings(**base)
    app = create_app(settings)
    migrate(app)
    with TestClient(app, base_url="https://api.example.invalid") as client:
        assert client.get("/api/health").status_code == 200
        assert (
            client.get("/api/health").headers["strict-transport-security"]
            == "max-age=31536000"
        )
        assert (
            client.get(
                "http://api.example.invalid/api/health",
                headers={"X-Forwarded-Proto": "https"},
            ).status_code
            == 400
        )


def test_budget_atomicity_and_persistence(tmp_path):
    app, settings = build(tmp_path, ai_daily_token_budget=42512)
    guard = app.state.ai_guard
    assert guard.reservation == 42512

    def reserve():
        try:
            guard.reserve_budget("admin")
            return "reserved"
        except WorkflowError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(lambda _: reserve(), range(4)))
    assert outcomes.count("reserved") == 1
    assert outcomes.count("budget_exhausted") == 3
    restarted = create_app(settings)
    with pytest.raises(WorkflowError, match="Daily application"):
        restarted.state.ai_guard.reserve_budget("admin")
    with app.state.engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT reserved_tokens FROM ai_daily_usage")
            ).scalar()
            == 42512
        )
    app.state.engine.dispose()
    restarted.state.engine.dispose()


def test_budget_storage_failure_closes_access(configured_app):
    app, _ = configured_app
    with app.state.engine.begin() as connection:
        connection.execute(text("DROP TABLE ai_daily_usage"))
    with pytest.raises(WorkflowError) as error:
        app.state.ai_guard.reserve_budget("admin")
    assert error.value.code == "budget_unavailable"


def test_ai_concurrency_rate_limits_and_no_refunds(tmp_path, frozen_rate_clock):
    app, _ = build(tmp_path, ai_rate_limit=2)
    guard = app.state.ai_guard
    with guard.request("admin"):
        with pytest.raises(WorkflowError) as error, guard.request("admin"):
            pytest.fail("A second concurrent request was admitted")
        assert error.value.code == "ai_busy"
    with pytest.raises(WorkflowError) as error, guard.request("admin"):
        pytest.fail("Rate limit was bypassed")
    assert error.value.code == "rate_limited"
    with app.state.engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT reserved_tokens FROM ai_daily_usage")
            ).scalar()
            == guard.reservation
        )
    app.state.engine.dispose()


def test_startup_missing_migrations_and_storage_warning(tmp_path, caplog):
    app = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'empty.db'}", password_hash=TEST_HASH
        )
    )
    with pytest.raises(RuntimeError, match="storage/schema"), TestClient(app):
        pass
    app.state.engine.dispose()
    app, _ = build(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
    assert "STORAGE NOT CONFIRMED PERSISTENT" in caplog.text


def test_budget_failure_prevents_provider_calls_and_does_not_refund(
    client, configured_app
):
    from unittest.mock import Mock

    from app.services.document_ai import ProviderRegistration

    app, _ = configured_app
    guard = app.state.ai_guard
    guard.settings = replace(guard.settings, ai_daily_token_budget=guard.reservation)
    provider = Mock()
    provider.query_terms.side_effect = WorkflowError(
        "provider_timeout", "Synthetic timeout", 504
    )
    factory = Mock(return_value=provider)
    app.state.document_providers["openai"] = ProviderRegistration(True, factory)
    document = client.post(
        "/api/documents",
        json={
            "title": "SYNTHETIC",
            "format": "text",
            "content": "Lifeboat inspection weekly.",
        },
    ).json()["id"]
    path = f"/api/documents/{document}/questions"
    payload = {
        "question": "lifeboat?",
        "model": "gpt-4.1-mini",
        "external_consent": False,
    }
    assert client.post(path, json=payload).status_code == 403
    factory.assert_not_called()
    payload["external_consent"] = True
    assert client.post(path, json=payload).status_code == 504
    response = client.post(path, json=payload)
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "budget_exhausted"
    assert factory.call_count == 1
    provider.close.assert_called_once()
    with app.state.engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT reserved_tokens FROM ai_daily_usage")
            ).scalar()
            == guard.reservation
        )


def test_backup_restore_preserves_originals_and_budget_but_revokes_sessions(
    client, configured_app, tmp_path
):
    import importlib.util
    from pathlib import Path

    app, settings = configured_app
    imported = client.post(
        "/api/documents",
        json={
            "title": "SYNTHETIC BACKUP",
            "format": "text",
            "content": "Synthetic immutable original.",
        },
    ).json()["id"]
    app.state.ai_guard.reserve_budget("admin")
    script = Path(__file__).resolve().parents[2] / "scripts" / "backup.py"
    spec = importlib.util.spec_from_file_location("backup_script", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "snapshot"
    from sqlalchemy.engine import make_url

    module.backup(
        Path(make_url(settings.database_url).database),
        app.state.document_directory,
        output,
    )
    assert (output / "COMPLETE").exists()
    assert (
        output / "originals" / (imported + ".bin")
    ).read_text() == "Synthetic immutable original."
    restored = create_app(
        replace(
            settings,
            database_url=f"sqlite:///{output / 'maritime.db'}",
            documents_dir=str(output / "originals"),
        )
    )
    with TestClient(restored) as second:
        second.headers.update({"Authorization": client.headers["Authorization"]})
        assert second.get("/api/documents").status_code == 401
        sign_in(second)
        assert second.get("/api/documents").json()[0]["id"] == imported
        with restored.state.engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT reserved_tokens FROM ai_daily_usage")
                ).scalar()
                == app.state.ai_guard.reservation
            )
    assert client.get("/api/documents").status_code == 200


def test_password_hash_and_session_forgery_are_rejected(client):
    with pytest.raises(ValueError):
        Settings(
            database_url="sqlite:////tmp/synthetic.db", password_hash="invalid-hash"
        )
    assert (
        client.get(
            "/api/vessels", headers={"Authorization": "Bearer forged-token"}
        ).status_code
        == 401
    )


def test_missing_original_volume_prevents_startup(client, configured_app):
    app, settings = configured_app
    document = client.post(
        "/api/documents",
        json={"title": "SYNTHETIC", "format": "text", "content": "Synthetic original"},
    ).json()["id"]
    (app.state.document_directory / (document + ".bin")).unlink()
    with (
        pytest.raises(RuntimeError, match="original document is missing"),
        TestClient(create_app(settings)),
    ):
        pass


def test_unexpected_errors_do_not_leak_sensitive_exception_text(
    configured_app, monkeypatch, caplog
):
    app, _ = configured_app

    def fail(request):
        raise RuntimeError("SENSITIVE-PASSWORD-AND-DOCUMENT")

    monkeypatch.setattr(app.state.auth, "authenticate", fail)
    with TestClient(app) as client:
        response = client.get("/api/documents")
        assert response.status_code == 500
        assert response.json()["detail"]["code"] == "internal_error"
        assert "SENSITIVE" not in response.text
    assert "SENSITIVE" not in caplog.text


def test_chunked_login_body_is_bounded_before_password_verification(
    configured_app, monkeypatch
):
    from unittest.mock import Mock

    app, _ = configured_app
    login = Mock()
    monkeypatch.setattr(app.state.auth, "login", login)
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            content=iter([b"x" * 2048] * 3),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 413
        login.assert_not_called()


def test_legacy_blob_originals_survive_security_migration(tmp_path):
    from uuid import uuid4

    from alembic import command
    from alembic.config import Config
    from app.db.session import create_database

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'legacy-original.db'}",
        password_hash=TEST_HASH,
    )
    engine, _ = create_database(settings.database_url)
    config = Config("alembic.ini")
    identifier = str(uuid4())
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
        connection.execute(
            text(
                "INSERT INTO documents(id,title,format,original,created_at) VALUES (:id,'SYNTHETIC LEGACY','text',:original,'2026-01-01')"
            ),
            {"id": identifier, "original": b"Synthetic legacy original"},
        )
        connection.execute(
            text(
                "INSERT INTO document_chunks(document_id,page,text) VALUES (:id,1,'Synthetic lifeboat evidence')"
            ),
            {"id": identifier},
        )
        command.upgrade(config, "head")
        assert (
            connection.execute(text("SELECT original FROM documents")).scalar()
            == b"Synthetic legacy original"
        )
        assert (
            connection.execute(text("SELECT original_path FROM documents")).scalar()
            is None
        )
    engine.dispose()
    with TestClient(create_app(settings)) as client:
        sign_in(client)
        assert client.get("/api/documents").json()[0]["id"] == identifier


def test_downgrade_refuses_to_discard_file_backed_original_metadata(
    client, configured_app
):
    from alembic import command
    from alembic.config import Config

    app, _ = configured_app
    assert (
        client.post(
            "/api/documents",
            json={
                "title": "SYNTHETIC",
                "format": "text",
                "content": "Synthetic original",
            },
        ).status_code
        == 201
    )
    config = Config("alembic.ini")
    with (
        pytest.raises(RuntimeError, match="Back up and restore"),
        app.state.engine.begin() as connection,
    ):
        config.attributes["connection"] = connection
        command.downgrade(config, "0002")
    assert client.get("/api/documents").status_code == 200


def test_synthetic_browser_harness_is_forbidden_in_production(monkeypatch):
    from browser_app import create_e2e_app

    monkeypatch.setenv("MARITIME_E2E_SYNTHETIC", "1")
    monkeypatch.setenv("MARITIME_ENV", "production")
    with pytest.raises(RuntimeError, match="forbidden outside development"):
        create_e2e_app()
