"""Synthetic local-only tests. PostgreSQL uses an explicitly supplied disposable URL."""

import base64
import hashlib
import os
import secrets
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from alembic import command
from alembic.config import Config
from botocore.stub import Stubber
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.gateway import consume_nonce
from app.core.object_storage import LocalStorage, S3Storage, unavailable, valid_key
from app.db.session import create_database, database_url
from app.main import create_app
from app.schemas.document import DocumentImport
from app.services import documents
from app.services.auth import rate_limit
from app.services.document_ai import ProviderRegistration, WorkflowError
from app.services.openai_provider import OpenAIProvider
from conftest import TEST_HASH, migrate, sign_in
from test_documents import make_pdf, completion
from test_gateway import HOST, SECRET, proof


class MemoryStorage:
    """Private in-memory S3 stand-in; deliberately can fail after a completed PUT."""

    def __init__(self):
        self.objects = {}
        self.fail_put = False
        self.fail_delete = False

    def put(self, key, content):
        self.objects[valid_key(key)] = content
        if self.fail_put:
            raise unavailable()

    def get(self, key):
        return self.objects[valid_key(key)]

    def size(self, key):
        return len(self.get(key))

    def delete(self, key):
        if self.fail_delete:
            raise unavailable()
        self.objects.pop(valid_key(key), None)

    def validate(self):
        pass


class GatewayAuth(httpx.Auth):
    def auth_flow(self, request):
        path = request.url.raw_path.decode()
        signed = proof(
            path,
            request.method,
            request.read(),
            {
                name: request.headers[name]
                for name in ("authorization", "content-type", "origin", "x-csrf-token")
                if name in request.headers
            },
        )
        request.headers.update(signed)
        yield request


def online_settings(**changes):
    return Settings(
        **(
            dict(
                online_mvp_mode=True,
                environment="production",
                https_transport="signed-gateway",
                gateway_secret=SECRET,
                database_url="postgresql://postgres:synthetic-test-only@127.0.0.1:55432/maritime_test?sslmode=verify-full",
                storage_backend="s3",
                storage_persistent=True,
                s3_private_bucket=True,
                s3_endpoint="https://synthetic.supabase.co/storage/v1/s3",
                s3_region="test-region",
                s3_bucket="private-documents",
                s3_access_key="synthetic",
                s3_secret_key="synthetic-secret",
                password_hash=TEST_HASH,
                trusted_hosts=(HOST,),
                allowed_origins=("https://maritime.example.workers.dev",),
                openai_api_key="",
                ai_enabled=False,
                upload_rate_limit=20,
            )
            | changes
        )
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"database_url": "sqlite:////tmp/ephemeral.db"},
        {"database_url": "postgresql://user:secret@host/db"},
        {"database_url": "postgresql://user:secret@host/db?sslmode=disable"},
        {"database_url": "postgresql://user:secret@host/db?sslmode=require"},
        {"environment": "development"},
        {"storage_backend": "local"},
        {"storage_persistent": False},
        {"s3_private_bucket": False},
        {"s3_endpoint": "http://synthetic.supabase.co"},
        {"s3_access_key": ""},
        {"s3_secret_key": ""},
        {"gateway_secret": ""},
        {"password_hash": ""},
        {"https_transport": "trusted-proxy"},
        {"auth_transport": "cookie"},
        {"trusted_hosts": ("*",)},
        {"allowed_origins": ("http://insecure.invalid",)},
        {"ai_enabled": True},
        {"ai_input_usd_per_million": "NaN"},
        {"max_documents": 21},
        {"openai_models": ("gpt-4.1-mini", "unpriced-model")},
    ],
)
def test_online_configuration_refuses_incomplete_persistence_or_security(changes):
    with pytest.raises(ValueError):
        online_settings(**changes)


def test_online_disabled_ai_needs_no_key_and_secrets_are_redacted():
    settings = online_settings()
    assert settings.mode == "online-mvp"
    assert settings.upload_bytes == 3_000_000
    assert "synthetic-secret" not in repr(settings)
    with pytest.raises(WorkflowError) as caught:
        OpenAIProvider(settings, settings.openai_model)
    assert caught.value.code == "paid_inference_disabled"


def test_postgresql_url_normalization_and_bounded_engine():
    assert database_url("postgres://user:secret@host/db").startswith(
        "postgresql+psycopg://"
    )
    engine, _ = create_database("postgresql://user:secret@127.0.0.1/db?sslmode=require")
    assert engine.pool.size() == 2
    assert engine.pool._max_overflow == 0
    assert engine.hide_parameters is True
    engine.dispose()
    with pytest.raises(ValueError):
        create_database("mysql://user@host/db")


@pytest.mark.parametrize(
    "key",
    [
        "../private.pdf",
        "/tmp/private",
        "a/../b",
        "..\\private",
        "00000000-0000-0000-0000-000000000000.pdf",
        "not-a-uuid.bin",
        "------------------------------------.bin",
    ],
)
def test_storage_keys_reject_path_traversal(tmp_path, key):
    storage = LocalStorage(tmp_path)
    for method, args in (
        (storage.put, (key, b"secret")),
        (storage.get, (key,)),
        (storage.delete, (key,)),
        (storage.size, (key,)),
    ):
        with pytest.raises(WorkflowError):
            method(*args)


def test_local_private_storage_collision_symlink_and_idempotent_delete(tmp_path):
    storage = LocalStorage(tmp_path)
    key = str(uuid4()) + ".bin"
    storage.put(key, b"synthetic")
    assert storage.size(key) == 9
    assert storage.get(key) == b"synthetic"
    if os.name != "nt":
        assert (tmp_path / key).stat().st_mode & 0o777 == 0o600
    with pytest.raises(WorkflowError):
        storage.put(key, b"overwrite")
    storage.delete(key)
    storage.delete(key)
    target = tmp_path / "sensitive"
    target.write_bytes(b"synthetic")
    try:
        (tmp_path / key).symlink_to(target)
    except OSError:
        pytest.skip("Symlinks unavailable on this platform")
    with pytest.raises(WorkflowError):
        storage.get(key)


def test_s3_calls_remain_private_and_failures_sanitized():
    settings = online_settings()
    storage = S3Storage(settings)
    client = storage.client
    assert client.meta.config.retries["total_max_attempts"] == 1
    key = str(uuid4()) + ".bin"
    with Stubber(client) as stub:
        stub.add_response("head_bucket", {}, {"Bucket": settings.s3_bucket})
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": settings.s3_bucket,
                "Key": key,
                "Body": b"synthetic",
                "ContentType": "application/octet-stream",
            },
        )
        stub.add_response(
            "head_object",
            {"ContentLength": 9},
            {"Bucket": settings.s3_bucket, "Key": key},
        )
        stub.add_response(
            "delete_object", {}, {"Bucket": settings.s3_bucket, "Key": key}
        )
        stub.add_client_error(
            "head_object",
            service_error_code="AccessDenied",
            service_message="SENSITIVE CREDENTIALS",
            expected_params={"Bucket": settings.s3_bucket, "Key": key},
        )
        storage.validate()
        storage.put(key, b"synthetic")
        assert storage.size(key) == 9
        storage.delete(key)
        with pytest.raises(WorkflowError) as caught:
            storage.size(key)
        assert "SENSITIVE" not in str(caught.value)
        stub.assert_no_pending_responses()
    client.close()


@pytest.fixture(params=["sqlite", "postgresql"])
def persistent_app(request, tmp_path, monkeypatch):
    storage = MemoryStorage()
    monkeypatch.setattr("app.main.create_storage", lambda *args: storage)
    admin_engine = None
    schema = None
    if request.param == "postgresql":
        url = os.environ.get("MARITIME_TEST_POSTGRES_URL")
        if not url:
            pytest.skip(
                "Set MARITIME_TEST_POSTGRES_URL to a disposable local PostgreSQL server"
            )
        parsed = make_url(database_url(url))
        if parsed.host not in {"localhost", "127.0.0.1"}:
            pytest.fail(
                "Integration tests require a local disposable PostgreSQL server"
            )
        admin_engine, _ = create_database(url)
        schema = "test_" + secrets.token_hex(8)
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        database = parsed.update_query_dict(
            {"options": f"-csearch_path={schema}", "sslmode": "verify-full"}
        ).render_as_string(hide_password=False)
        settings = online_settings(database_url=database)
    else:
        settings = Settings(
            database_url=f"sqlite:///{tmp_path / 'test.db'}",
            password_hash=TEST_HASH,
            upload_rate_limit=20,
        )
    app = create_app(settings)
    migrate(app)
    try:
        with TestClient(
            app,
            base_url="http://" + HOST
            if settings.online_mvp_mode
            else "http://testserver",
        ) as client:
            client.auth = GatewayAuth() if settings.online_mvp_mode else None
            sign_in(client)
            yield app, settings, client, storage
    finally:
        app.state.engine.dispose()
        if admin_engine:
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin_engine.dispose()


def upload(client, title="SYNTHETIC PDF"):
    raw = make_pdf()
    response = client.post(
        "/api/documents",
        json={
            "title": title,
            "format": "pdf",
            "content": base64.b64encode(raw).decode(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), raw


def test_pdf_metadata_search_sources_delete_and_index_cleanup(persistent_app):
    app, settings, client, storage = persistent_app
    document, raw = upload(client)
    assert document["sha256"] == hashlib.sha256(raw).hexdigest()
    assert document["byte_size"] == len(raw)
    assert document["page_count"] == 1
    assert document["state"] == "ready"
    results = client.get(f"/api/documents/{document['id']}/search?q=lifeboat").json()
    assert len(results) == 1
    excerpt = client.get(
        f"/api/documents/{document['id']}/excerpts/{results[0]['excerpt_id']}"
    )
    assert excerpt.json()["page"] == 1
    assert "lifeboat" in excerpt.json()["text"]
    original = client.get(f"/api/documents/{document['id']}/original")
    assert original.content == raw
    assert original.headers["content-type"] == "application/octet-stream"
    assert "attachment" in original.headers["content-disposition"]
    deleted = client.request("DELETE", f"/api/documents/{document['id']}", json={})
    assert deleted.status_code == 200, deleted.text
    assert storage.objects == {}
    assert (
        client.get(f"/api/documents/{document['id']}/search?q=lifeboat").status_code
        == 404
    )
    with app.state.engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM document_chunks")).scalar()
            == 0
        )
        if connection.dialect.name == "sqlite":
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM document_fts WHERE document_fts MATCH 'lifeboat'"
                    )
                ).scalar()
                == 0
            )


def test_document_and_ship_ownership_all_routes_fail_closed(persistent_app):
    app, settings, client, storage = persistent_app
    document, _ = upload(client)
    vessel = client.post(
        "/api/vessels",
        json={"vessel_name": "SYNTHETIC OWNER", "length_overall": "123.456"},
    ).json()
    with app.state.engine.begin() as connection:
        connection.execute(text("UPDATE documents SET owner_id='other-owner'"))
        connection.execute(text("UPDATE vessels SET owner_id='other-owner'"))
    assert client.get("/api/documents").json() == []
    assert client.get("/api/vessels").json() == []
    for suffix in ("original", "search?q=lifeboat", "excerpts/1"):
        assert (
            client.get(f"/api/documents/{document['id']}/{suffix}").status_code == 404
        )
    assert (
        client.request(
            "DELETE", f"/api/documents/{document['id']}", json={}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/documents/{document['id']}/questions",
            json={
                "question": "lifeboat?",
                "model": settings.openai_model,
                "external_consent": True,
            },
        ).status_code
        == 404
    )
    assert client.get(f"/api/vessels/{vessel['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/vessels/{vessel['id']}", json={"flag": "SYNTHETIC"}
        ).status_code
        == 404
    )
    assert storage.objects


def test_interrupted_upload_and_deletion_are_recoverable(persistent_app):
    app, settings, client, storage = persistent_app
    storage.fail_put = True
    response = client.post(
        "/api/documents",
        json={
            "title": "SYNTHETIC INTERRUPTED",
            "format": "text",
            "content": "Synthetic lifeboat weekly",
        },
    )
    assert response.status_code == 503
    item = client.get("/api/documents").json()[0]
    assert item["state"] == "pending"
    assert storage.objects
    assert (
        client.get(f"/api/documents/{item['id']}/search?q=lifeboat").status_code == 409
    )
    storage.fail_delete = True
    assert (
        client.request("DELETE", f"/api/documents/{item['id']}", json={}).status_code
        == 503
    )
    assert client.get("/api/documents").json()[0]["state"] == "deleting"
    storage.fail_delete = False
    assert (
        client.request("DELETE", f"/api/documents/{item['id']}", json={}).status_code
        == 200
    )
    assert client.get("/api/documents").json() == []
    assert not storage.objects


def test_ship_profile_persistence_and_restart(persistent_app, monkeypatch):
    app, settings, client, storage = persistent_app
    vessel = client.post(
        "/api/vessels",
        json={
            "vessel_name": "SYNTHETIC RESTART",
            "imo_number": "0000000",
            "length_overall": "123.456",
        },
    ).json()
    response = client.patch(
        f"/api/vessels/{vessel['id']}", json={"flag": "SYNTHETIC FLAG"}
    )
    assert response.status_code == 200
    assert (
        response.json()["field_provenance"]["flag"]["verification_status"]
        == "unverified"
    )
    second = create_app(settings)
    with TestClient(
        second,
        base_url="http://" + HOST if settings.online_mvp_mode else "http://testserver",
    ) as restarted:
        restarted.auth = GatewayAuth() if settings.online_mvp_mode else None
        sign_in(restarted)
        saved = restarted.get(f"/api/vessels/{vessel['id']}").json()
        assert saved["flag"] == "SYNTHETIC FLAG"
        assert saved["length_overall"] == "123.456"
        assert saved["imo_number"] == "0000000"


def test_quota_and_nonce_atomicity_real_dialects(persistent_app):
    app, settings, client, storage = persistent_app
    guard = app.state.ai_guard
    guard.settings = replace(settings, ai_daily_token_budget=guard.reservation)

    def reserve(_):
        try:
            guard.reserve_budget("admin")
            return "reserved"
        except WorkflowError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(reserve, range(4)))
    assert sorted(outcomes) == ["budget_exhausted"] * 3 + ["reserved"]
    nonce = secrets.token_hex(16)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert (
            sum(
                pool.map(
                    lambda _: consume_nonce(
                        app.state.engine, nonce, datetime.now(UTC).timestamp()
                    ),
                    range(4),
                )
            )
            == 1
        )
    rate_limit(app.state.engine, "test:atomic", 1)
    with pytest.raises(WorkflowError) as caught:
        rate_limit(app.state.engine, "test:atomic", 1)
    assert caught.value.code == "rate_limited"


def test_usage_tracking_cost_and_failed_ledger(persistent_app):
    app, settings, client, storage = persistent_app
    guard = app.state.ai_guard
    guard.reserve_budget("admin")
    guard.record_usage(
        "admin", settings.openai_model, {"input_tokens": 1000, "output_tokens": 500}
    )
    result = client.get("/api/ai/usage").json()
    assert result["input_tokens"] == 1000
    assert result["output_tokens"] == 500
    assert result["requests"] == 1
    assert result["estimated_recorded_cost_usd"] == "0.0012"
    assert result["reserved_tokens"] == guard.reservation
    with app.state.engine.begin() as connection:
        connection.execute(text("DROP TABLE ai_daily_usage"))
    with pytest.raises(WorkflowError) as caught:
        guard.record_usage(
            "admin", settings.openai_model, {"input_tokens": 1, "output_tokens": 1}
        )
    assert caught.value.code == "usage_unavailable"


def test_online_inference_is_opt_in_and_upload_quota(persistent_app):
    app, settings, client, storage = persistent_app
    if not settings.online_mvp_mode:
        return
    document, _ = upload(client)
    provider = Mock()
    factory = Mock(return_value=provider)
    app.state.document_providers["openai"] = ProviderRegistration(True, factory)
    response = client.post(
        f"/api/documents/{document['id']}/questions",
        json={
            "question": "lifeboat?",
            "model": settings.openai_model,
            "external_consent": True,
        },
    )
    assert response.status_code == 403
    factory.assert_not_called()
    with app.state.engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM ai_daily_usage")).scalar()
            == 0
        )
    app.state.settings = replace(settings, max_documents=1)
    # Router captures immutable settings; test service's count check directly.
    with pytest.raises(WorkflowError) as caught:
        documents.import_document(
            app.state.sessions,
            DocumentImport(title="Synthetic", format="text", content="Synthetic"),
            owner="admin",
            storage=storage,
            settings=replace(settings, max_documents=1),
        )
    assert caught.value.code == "document_quota"


def test_isolated_parser_limits_and_timeout(monkeypatch):
    pdf = DocumentImport(
        title="Synthetic", format="pdf", content=base64.b64encode(make_pdf()).decode()
    )
    original, pages = documents.isolated_extract(pdf)
    assert original.startswith(b"%PDF-")
    assert pages[0][0] == 1
    assert "lifeboat" in pages[0][1]
    with pytest.raises(WorkflowError) as caught:
        documents.isolated_extract(
            DocumentImport(
                title="Synthetic",
                format="pdf",
                content=base64.b64encode(b"%PDF-" + b"x" * 3_000_000).decode(),
            )
        )
    assert caught.value.code == "document_too_large"
    monkeypatch.setattr(
        documents.subprocess,
        "run",
        Mock(side_effect=subprocess.TimeoutExpired("synthetic", 20)),
    )
    with pytest.raises(WorkflowError) as caught:
        documents.isolated_extract(pdf)
    assert caught.value.code == "pdf_processing_timeout"


def test_pdf_page_and_encryption_limits():
    from io import BytesIO
    from pypdf import PdfWriter

    for encrypted in (False, True):
        writer = PdfWriter()
        for _ in range(1 if encrypted else 51):
            writer.add_blank_page(width=100, height=100)
        if encrypted:
            writer.encrypt("synthetic")
        output = BytesIO()
        writer.write(output)
        payload = DocumentImport(
            title="Synthetic",
            format="pdf",
            content=base64.b64encode(output.getvalue()).decode(),
        )
        with pytest.raises(WorkflowError) as caught:
            documents.isolated_extract(payload)
        assert caught.value.code == "invalid_document"


def test_sdk_mocked_paid_workflow_records_both_calls_and_citations(persistent_app):
    from openai import OpenAI

    app, settings, client, storage = persistent_app
    enabled = replace(settings, ai_enabled=True, openai_api_key="synthetic-only")
    app.state.ai_guard.settings = enabled
    seen = []

    def handle(request):
        import json

        data = json.loads(json.loads(request.content)["messages"][1]["content"])
        seen.append(data)
        if "evidence" in data:
            content = {
                "status": "answered",
                "claims": [
                    {
                        "text": "Weekly in this synthetic exercise.",
                        "excerpt_id": data["evidence"][0]["excerpt_id"],
                        "quote": "Synthetic lifeboat inspections weekly.",
                    }
                ],
            }
        else:
            content = {
                "english": "lifeboat inspections",
                "vietnamese": "xuồng cứu sinh",
            }
        return httpx.Response(
            200,
            json=completion(content)
            | {
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "total_tokens": 120,
                }
            },
        )

    def factory(model):
        provider = OpenAIProvider(enabled, model)
        provider.client.close()
        provider.client = OpenAI(
            api_key="synthetic-only",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
        )
        return provider

    app.state.document_providers["openai"] = ProviderRegistration(True, factory)
    document, _ = upload(client)
    response = client.post(
        f"/api/documents/{document['id']}/questions",
        json={
            "question": "lifeboat inspections?",
            "model": settings.openai_model,
            "external_consent": True,
        },
    )
    assert response.status_code == 200, response.text
    assert len(seen) == 2
    claim = response.json()["claims"][0]
    assert claim["source"]["document_id"] == document["id"]
    assert claim["source"]["page"] == 1
    usage = client.get("/api/ai/usage").json()
    assert usage["input_tokens"] == 200
    assert usage["output_tokens"] == 40
    assert usage["requests"] == 2
    assert usage["reserved_tokens"] == app.state.ai_guard.reservation


def test_online_large_signed_upload_and_unchanged_authentication(persistent_app):
    app, settings, client, storage = persistent_app
    if not settings.online_mvp_mode:
        return
    with TestClient(app, base_url="http://" + HOST) as direct:
        assert direct.get("/api/health").status_code == 401
        assert (
            direct.get(
                "/api/documents",
                headers={"X-Maritime-User": "admin", "X-Forwarded-Proto": "https"},
            ).status_code
            == 401
        )
    response = client.post(
        "/api/documents",
        json={
            "title": "SYNTHETIC LARGE",
            "format": "text",
            "content": "Synthetic lifeboat weekly. " * 3000,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["byte_size"] > 65536
    assert (
        client.post("/api/vessels", json={"vessel_name": "x" * 65536}).status_code
        == 401
    )


def test_online_startup_rejects_missing_original_and_unowned_data(persistent_app):
    app, settings, client, storage = persistent_app
    if not settings.online_mvp_mode:
        return
    document, _ = upload(client)
    storage.objects.clear()
    with (
        pytest.raises(RuntimeError, match="original document is missing"),
        TestClient(create_app(settings)),
    ):
        pass
    with app.state.engine.begin() as connection:
        connection.execute(text("UPDATE documents SET owner_id=NULL"))
    with (
        pytest.raises(RuntimeError, match="unowned/legacy"),
        TestClient(create_app(settings)),
    ):
        pass


def test_postgresql_migration_round_trip_and_search_index(persistent_app):
    app, settings, client, storage = persistent_app
    if not settings.online_mvp_mode:
        return
    config = Config("alembic.ini")
    with app.state.engine.begin() as connection:
        config.attributes["connection"] = connection
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind='r' AND NOT relrowsecurity"
                )
            ).scalar()
            == 0
        )
        assert "document_fts" not in inspect(connection).get_table_names()
        assert "ix_chunks_search" in {
            index["name"]
            for index in inspect(connection).get_indexes("document_chunks")
        }
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        assert "vessels" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            == "0004"
        )


def test_online_environment_flags_do_not_silently_fall_back(monkeypatch):
    monkeypatch.setenv("MARITIME_ONLINE_MVP_MODE", "typo")
    with pytest.raises(ValueError, match="true or false"):
        Settings(database_url="sqlite:////tmp/synthetic.db")
    monkeypatch.setenv("MARITIME_ONLINE_MVP_MODE", "true")
    monkeypatch.delenv("MARITIME_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="no SQLite fallback"):
        Settings()


def test_active_upload_cannot_be_deleted_or_overlapped(persistent_app):
    app, settings, client, storage = persistent_app
    document, _ = upload(client)
    assert app.state.upload_slot.acquire(blocking=False)
    try:
        assert (
            client.request(
                "DELETE", f"/api/documents/{document['id']}", json={}
            ).status_code
            == 429
        )
        response = client.post(
            "/api/documents",
            json={
                "title": "Synthetic blocked",
                "format": "text",
                "content": "Synthetic",
            },
        )
        assert response.status_code == 429
        assert len(storage.objects) == 1
    finally:
        app.state.upload_slot.release()


def test_postgresql_rls_denies_a_browserlike_role_even_with_select(persistent_app):
    app, settings, client, storage = persistent_app
    if not settings.online_mvp_mode:
        return
    upload(client)
    role = "browser_test_" + secrets.token_hex(8)
    with app.state.engine.begin() as connection:
        schema = connection.execute(text("SELECT current_schema()")).scalar_one()
        connection.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
        connection.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
        connection.execute(text(f'GRANT SELECT ON documents TO "{role}"'))
        connection.execute(text(f'SET LOCAL ROLE "{role}"'))
        assert connection.execute(text("SELECT count(*) FROM documents")).scalar() == 0
        connection.execute(text("RESET ROLE"))
        connection.execute(text(f'DROP OWNED BY "{role}"'))
        connection.execute(text(f'DROP ROLE "{role}"'))


def test_postgresql_migrations_can_render_for_review_without_connecting(monkeypatch):
    from io import StringIO

    monkeypatch.setenv(
        "MARITIME_DATABASE_URL",
        "postgresql://synthetic:synthetic@unreachable.invalid/test",
    )
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE VIRTUAL TABLE" not in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "to_tsvector" in sql
    assert "USING gin" in sql


def test_indexing_failure_keeps_tracked_original_and_pending_row(persistent_app):
    from sqlalchemy import event
    from sqlalchemy.exc import SQLAlchemyError
    from app.models.document import DocumentChunk

    app, settings, client, storage = persistent_app

    def fail(*args):
        raise SQLAlchemyError("SENSITIVE-DOCUMENT-MARKER")

    event.listen(DocumentChunk, "before_insert", fail)
    try:
        raw = make_pdf()
        response = client.post(
            "/api/documents",
            json={
                "title": "SYNTHETIC INDEX FAILURE",
                "format": "pdf",
                "content": base64.b64encode(raw).decode(),
            },
        )
        assert response.status_code == 503
        assert "SENSITIVE" not in response.text
    finally:
        event.remove(DocumentChunk, "before_insert", fail)
    items = client.get("/api/documents").json()
    assert len(items) == 1
    assert items[0]["state"] == "pending"
    assert len(storage.objects) == 1
    with app.state.engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM document_chunks")).scalar()
            == 0
        )
    assert (
        client.request(
            "DELETE", f"/api/documents/{items[0]['id']}", json={}
        ).status_code
        == 200
    )
    assert not storage.objects


def test_tampered_original_is_withheld(persistent_app):
    app, settings, client, storage = persistent_app
    document, original = upload(client)
    storage.objects[document["id"] + ".bin"] = b"x" * len(original)
    response = client.get(f"/api/documents/{document['id']}/original")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "storage_integrity_failed"
