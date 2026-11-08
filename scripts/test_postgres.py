"""Run synthetic integration tests in a disposable local Docker PostgreSQL.

Requires Linux, Docker's managed local socket and OpenSSL. Never uses a cloud DB.
The container, certificate and password are discarded even if tests fail.
"""

import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ["docker", "--host=unix:///var/run/docker.sock"]


def run(*args, **kwargs):
    return subprocess.run([*args], check=True, capture_output=True, text=True, **kwargs)


def main():
    for selector in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        os.environ.pop(selector, None)
    container = "maritime-mvp-tests-" + secrets.token_hex(6)
    password = secrets.token_urlsafe(24)
    try:
        run(
            *DOCKER,
            "run",
            "--rm",
            "-d",
            "--name",
            container,
            "-e",
            f"POSTGRES_PASSWORD={password}",
            "-e",
            "POSTGRES_DB=maritime_test",
            "-p",
            "127.0.0.1::5432",
            "postgres:17-alpine",
        )
        for attempt in range(100):
            ready = subprocess.run(
                [*DOCKER, "exec", container, "pg_isready", "-U", "postgres"],
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Disposable PostgreSQL did not become ready")
        with tempfile.TemporaryDirectory(prefix="maritime-pg-tls-") as directory:
            cert, key = Path(directory) / "server.crt", Path(directory) / "server.key"
            run(
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            )
            for file in (cert, key):
                run(*DOCKER, "cp", str(file), f"{container}:/tmp/{file.name}")
            run(
                *DOCKER,
                "exec",
                container,
                "chown",
                "postgres:postgres",
                "/tmp/server.key",
                "/tmp/server.crt",
            )
            run(*DOCKER, "exec", container, "chmod", "600", "/tmp/server.key")
            for sql in (
                "ALTER SYSTEM SET ssl='on'",
                "ALTER SYSTEM SET ssl_cert_file='/tmp/server.crt'",
                "ALTER SYSTEM SET ssl_key_file='/tmp/server.key'",
                "SELECT pg_reload_conf()",
            ):
                run(*DOCKER, "exec", "-u", "postgres", container, "psql", "-c", sql)
            port = (
                run(*DOCKER, "port", container, "5432/tcp")
                .stdout.strip()
                .rsplit(":", 1)[1]
            )
            query = urlencode({"sslmode": "verify-full", "sslrootcert": str(cert)})
            url = f"postgresql://postgres:{password}@localhost:{port}/maritime_test?{query}"
            environment = os.environ | {"MARITIME_TEST_POSTGRES_URL": url}
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    *(
                        sys.argv[1:]
                        or [
                            "-q",
                            "tests/test_online_mvp.py",
                            "tests/test_supabase_staging.py",
                        ]
                    ),
                ],
                cwd=ROOT / "backend",
                env=environment,
            ).returncode
    finally:
        subprocess.run([*DOCKER, "rm", "-f", container], capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())
