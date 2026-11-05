"""Cross-language request signing over real, certificate-verified local TLS."""

import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from app.core.config import Settings
from app.core.disposable import DISABLED_API_KEY, DISPOSABLE_ACK
from app.main import create_app
from conftest import TEST_HASH, migrate


def test_worker_to_backend_over_verified_tls(tmp_path):
    if not shutil.which("node") or not shutil.which("openssl"):
        pytest.skip("Node and OpenSSL required for cross-language TLS integration")
    repo = Path(__file__).resolve().parents[2]
    gateway = repo / "deploy/gateway"
    if not (gateway / "dist/index.js").exists():
        # Compile using the existing locked TypeScript toolchain, never install packages here.
        compiler = repo / "frontend/node_modules/typescript/bin/tsc"
        if not compiler.exists():
            pytest.skip("Install locked frontend dependencies to run TLS integration")
        subprocess.run(
            ["node", str(compiler), "-p", str(gateway / "tsconfig.json")], check=True
        )
    cert, key = tmp_path / "ca.crt", tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1,DNS:backend.example.onrender.com",
        ],
        check=True,
        capture_output=True,
    )
    with tempfile.TemporaryDirectory(prefix="maritime-disposable-") as directory:
        root = Path(directory)
        app = create_app(
            Settings(
                environment="production",
                https_transport="signed-gateway",
                gateway_secret="00" * 32,
                password_hash=TEST_HASH,
                openai_api_key=DISABLED_API_KEY,
                database_url=f"sqlite:///{root / 'maritime.db'}",
                documents_dir=str(root / "originals"),
                trusted_hosts=("backend.example.onrender.com",),
                allowed_origins=("https://maritime.example.workers.dev",),
                storage_persistent=False,
                disposable_test_mode=True,
                disposable_ack=DISPOSABLE_ACK,
                disposable_root=directory,
            )
        )
        migrate(app)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            server = uvicorn.Server(
                uvicorn.Config(
                    app,
                    proxy_headers=False,
                    forwarded_allow_ips="",
                    log_level="error",
                    ssl_certfile=str(cert),
                    ssl_keyfile=str(key),
                )
            )
            thread = threading.Thread(
                target=server.run, kwargs={"sockets": [sock]}, daemon=True
            )
            thread.start()
            try:
                for _ in range(100):
                    if server.started:
                        break
                    time.sleep(0.05)
                assert server.started
                result = subprocess.run(
                    [
                        "node",
                        str(gateway / "tests/integration-client.mjs"),
                    ],
                    check=False,
                    env=os.environ
                    | {
                        "NODE_EXTRA_CA_CERTS": str(cert),
                        "MARITIME_TEST_TLS_ORIGIN": f"https://127.0.0.1:{port}",
                    },
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                assert result.returncode == 0, result.stdout + result.stderr
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                assert not thread.is_alive()
