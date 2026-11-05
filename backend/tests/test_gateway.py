import hashlib
import hmac
import json
import secrets
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from app.core.config import Settings
from app.core.disposable import DISABLED_API_KEY, DISPOSABLE_ACK, SYNTHETIC_DOCUMENT
from app.core.gateway import canonical_message
from app.main import create_app
from conftest import TEST_HASH, TEST_PASSWORD, migrate
from fastapi.testclient import TestClient

SECRET = "00" * 32  # Synthetic credential, never a deployment default.
HOST = "backend.example.onrender.com"


def proof(
    path="/api/health", method="GET", body=b"", headers=None, stamp=None, nonce=None
):
    split = urlsplit(path)
    values = {
        b"host": HOST.encode(),
        b"x-maritime-gateway-time": str(stamp or int(time.time())).encode(),
        b"x-maritime-gateway-nonce": (nonce or secrets.token_hex(16)).encode(),
    }
    values.update({k.lower().encode(): v.encode() for k, v in (headers or {}).items()})
    scope = {
        "method": method,
        "raw_path": split.path.encode(),
        "query_string": split.query.encode(),
    }
    signature = hmac.new(
        bytes.fromhex(SECRET), canonical_message(scope, values, body), hashlib.sha256
    ).hexdigest()
    return {k.decode(): v.decode() for k, v in values.items()} | {
        "x-maritime-gateway-signature": signature
    }


@pytest.fixture
def gateway_app():
    with tempfile.TemporaryDirectory(prefix="maritime-disposable-") as directory:
        root = Path(directory)
        settings = Settings(
            environment="production",
            https_transport="signed-gateway",
            gateway_secret=SECRET,
            password_hash=TEST_HASH,
            openai_api_key=DISABLED_API_KEY,
            database_url=f"sqlite:///{root / 'maritime.db'}",
            documents_dir=str(root / "originals"),
            trusted_hosts=(HOST,),
            allowed_origins=("https://maritime.example.workers.dev",),
            storage_persistent=False,
            disposable_test_mode=True,
            disposable_ack=DISPOSABLE_ACK,
            disposable_root=directory,
        )
        app = create_app(settings)
        migrate(app)
        yield app, settings


def test_independent_wire_vector():
    vector = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "deploy/gateway/protocol-v1.test-vector.json"
        ).read_text()
    )
    url = urlsplit(vector["url"])
    headers = proof(
        url.path + "?" + url.query,
        vector["method"],
        vector["body"].encode(),
        vector["headers"],
        int(vector["timestamp"]),
        vector["nonce"],
    )
    assert headers["x-maritime-gateway-signature"] == vector["signature"]


def test_unsigned_and_proxy_spoofed_requests_cannot_reach_app(gateway_app):
    with TestClient(gateway_app[0], base_url="http://" + HOST) as client:
        for path in ("/api/health", "/api/documents"):
            for headers in (
                {},
                {"X-Forwarded-Proto": "https", "X-Forwarded-For": "127.0.0.1"},
            ):
                assert client.get(path, headers=headers).status_code == 401
        assert (
            client.options(
                "/api/documents",
                headers={
                    "Origin": "https://maritime.example.workers.dev",
                    "Access-Control-Request-Method": "POST",
                },
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/health", headers=proof() | {"host": "evil.invalid"}
            ).status_code
            == 400
        )
        assert (
            client.get(
                "/api/health", headers=proof() | {"X-Forwarded-Proto": "http"}
            ).status_code
            == 200
        )
        assert (
            client.get("/api/documents", headers=proof("/api/documents")).status_code
            == 401
        )
        assert (
            client.get(
                "/api/health", headers=proof(headers={"origin": "https://evil.invalid"})
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"gateway_secret": ""},
        {"gateway_secret": "a" * 63},
        {"gateway_secret": "G" * 64},
        {"environment": "development"},
        {"disposable_test_mode": False},
        {"https_transport": "unknown"},
        {"https_transport": "trusted-proxy"},
    ],
)
def test_gateway_configuration_fails_closed(gateway_app, changes):
    with pytest.raises(ValueError):
        replace(gateway_app[1], **changes)


def test_gateway_rejects_proxy_trust_configuration(gateway_app, monkeypatch):
    monkeypatch.setenv("MARITIME_TRUSTED_PROXY_IPS", "127.0.0.1")
    with pytest.raises(ValueError):
        replace(gateway_app[1])


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorization", "Bearer forged"),
        ("origin", "https://evil.invalid"),
        ("content-type", "text/plain"),
        ("x-csrf-token", "forged"),
        ("x-maritime-gateway-signature", "ff" * 32),
    ],
)
def test_modified_signed_fields_are_rejected(gateway_app, field, value):
    with TestClient(gateway_app[0], base_url="http://" + HOST) as client:
        assert (
            client.get("/api/health", headers=proof() | {field: value}).status_code
            == 401
        )


def test_path_method_body_clock_and_duplicate_proofs_are_bound(gateway_app):
    with TestClient(gateway_app[0], base_url="http://" + HOST) as client:
        for skew in (-180, 60):
            assert (
                client.get(
                    "/api/health", headers=proof(stamp=int(time.time()) + skew)
                ).status_code
                == 401
            )
        assert client.get("/api/health?changed=1", headers=proof()).status_code == 401
        assert client.get("/api/documents", headers=proof()).status_code == 401
        assert (
            client.post(
                "/api/health", content=b"changed", headers=proof(method="POST")
            ).status_code
            == 401
        )
        assert client.post("/api/health", headers=proof()).status_code == 401
        duplicated = list(proof().items()) + [
            ("x-maritime-gateway-time", str(int(time.time())))
        ]
        assert client.get("/api/health", headers=duplicated).status_code == 401
        body = b"x" * 65537
        assert (
            client.post(
                "/api/health", content=body, headers=proof(method="POST", body=body)
            ).status_code
            == 401
        )


def test_replay_and_storage_failure_deny_access(gateway_app):
    with TestClient(gateway_app[0], base_url="http://" + HOST) as client:
        signed = proof()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: client.get("/api/health", headers=signed).status_code,
                    range(2),
                )
            )
        assert sorted(results) == [200, 401]
        with gateway_app[0].state.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE rate_windows")
        assert client.get("/api/health", headers=proof()).status_code == 401


def test_nonce_retention_outlives_expiry_and_existing_auth_cleanup(
    gateway_app, monkeypatch
):
    # Worst case: consumed at a minute boundary with a timestamp 5 seconds ahead.
    clock = [int(time.time()) // 60 * 60 + 59]
    monkeypatch.setattr("app.core.gateway.time.time", lambda: clock[0])
    signed = proof(stamp=clock[0] + 5)
    with TestClient(gateway_app[0], base_url="http://" + HOST) as client:
        assert client.get("/api/health", headers=signed).status_code == 200
        clock[0] += 124  # Proof remains valid, but must already be consumed.
        with gateway_app[0].state.engine.begin() as connection:
            from sqlalchemy import text

            connection.execute(
                text("DELETE FROM rate_windows WHERE window < :old"),
                {"old": clock[0] // 60 - 2},
            )
        assert client.get("/api/health", headers=signed).status_code == 401


def test_gateway_preserves_owner_auth_and_disposable_restrictions(gateway_app):
    with TestClient(gateway_app[0], base_url="http://" + HOST) as client:

        def post(path, payload, token=None):
            body = json.dumps(payload).encode()
            headers = {"content-type": "application/json"}
            if token:
                headers["authorization"] = "Bearer " + token
            return client.post(
                path, content=body, headers=proof(path, "POST", body, headers)
            )

        denied = post(
            "/api/auth/login", {"username": "admin", "password": "wrong-password"}
        )
        assert denied.status_code == 401
        login = post(
            "/api/auth/login", {"username": "admin", "password": TEST_PASSWORD}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        sample = post("/api/documents", SYNTHETIC_DOCUMENT, token)
        assert sample.status_code == 201
        assert (
            post("/api/vessels", {"vessel_name": "SYNTHETIC"}, token).status_code == 403
        )
        assert (
            post(
                f"/api/documents/{sample.json()['id']}/questions",
                {
                    "question": "Synthetic only",
                    "model": "gpt-4.1-mini",
                    "external_consent": True,
                },
                token,
            ).status_code
            == 403
        )
        assert (
            post(
                "/api/documents",
                SYNTHETIC_DOCUMENT | {"content": "real content forbidden"},
                token,
            ).status_code
            == 422
        )
