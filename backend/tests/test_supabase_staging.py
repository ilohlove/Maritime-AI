"""Synthetic tests against only the disposable local TLS PostgreSQL runner."""

import importlib.util
import os
from pathlib import Path
import secrets

from alembic import command
from alembic.config import Config
import psycopg
from psycopg import sql
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.db.session import database_url

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "scripts" / "supabase"
TABLES = (
    "vessels",
    "documents",
    "document_chunks",
    "auth_sessions",
    "rate_windows",
    "ai_daily_usage",
    "alembic_version",
)


def test_probe_rejects_insecure_configuration(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "probe", SQL / "validate_connection.py"
    )
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    ca = tmp_path / "ca.pem"
    ca.write_text("synthetic placeholder; not used for a connection")
    env = dict(
        PGHOST="pooler.example.invalid",
        PGPORT="5432",
        PGUSER="maritime_backend.PROJECT",
        PGDATABASE="postgres",
        PGSSLMODE="verify-full",
        PGSSLROOTCERT=str(ca),
    )
    assert probe.connection_parameters(env)["sslmode"] == "verify-full"
    for change in (
        {"PGSSLMODE": "require"},
        {"PGSSLMODE": "disable"},
        {"PGPORT": "6543"},
        {"PGHOST": "127.0.0.1"},
        {"PGHOST": "a,b"},
        {"PGSSLROOTCERT": "/missing/ca.pem"},
    ):
        with pytest.raises(ValueError):
            probe.connection_parameters(env | change)


@pytest.fixture(scope="module")
def staging():
    url = os.environ.get("MARITIME_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Run python scripts/test_postgres.py for local TLS PostgreSQL")
    parsed = make_url(database_url(url))
    assert parsed.host in {
        "localhost",
        "127.0.0.1",
    }, "Local disposable database required"
    assert parsed.database == "maritime_test", "Disposable database required"
    admin = create_engine(parsed)
    owner_password, backend_password = secrets.token_urlsafe(24), secrets.token_urlsafe(
        24
    )
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        raw = c.connection.driver_connection
        for role in ("anon", "authenticated"):
            raw.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role)))
        # Simulate Supabase's default browser grants; bootstrap must revoke these.
        raw.execute("CREATE ROLE staging_admin LOGIN CREATEROLE NOINHERIT")
        raw.execute("ALTER SCHEMA public OWNER TO staging_admin")
        raw.execute("SET ROLE staging_admin")
        raw.execute("CREATE ROLE maritime_migrator LOGIN NOINHERIT")
        raw.execute("RESET ROLE")
        raw.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE maritime_migrator GRANT ALL ON TABLES TO anon, authenticated"
        )
        raw.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE maritime_migrator IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated"
        )
        raw.execute("SET ROLE staging_admin")
        for _ in range(2):
            raw.execute((SQL / "01_roles.sql").read_text())
        for role, password in (
            ("maritime_migrator", owner_password),
            ("maritime_backend", backend_password),
        ):
            raw.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
        raw.execute("RESET ROLE")
    owner = create_engine(
        parsed.set(username="maritime_migrator", password=owner_password)
    )
    backend = create_engine(
        parsed.set(username="maritime_backend", password=backend_password)
    )
    with owner.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        for _ in range(2):
            c.connection.driver_connection.execute(
                (SQL / "01b_migration_defaults.sql").read_text()
            )
    config = Config("alembic.ini")
    with owner.begin() as c:
        config.attributes["connection"] = c
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    # Inject a failed migration and verify PostgreSQL transactional DDL rollback.
    with pytest.raises(Exception, match="synthetic migration failure"):
        with owner.begin() as c:
            c.execute(text("CREATE TABLE synthetic_rollback (id integer)"))
            raise RuntimeError("synthetic migration failure")
    with owner.connect() as c:
        assert (
            c.execute(text("SELECT to_regclass('public.synthetic_rollback')")).scalar()
            is None
        )
    for _ in range(2):
        with owner.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            c.connection.driver_connection.execute(
                (SQL / "02_application_access.sql").read_text()
            )
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.connection.driver_connection.execute((SQL / "03_verify.sql").read_text())
    yield admin, owner, backend, parsed.set(
        username="maritime_backend", password=backend_password
    )
    backend.dispose()
    owner.dispose()
    # This cluster is destroyed by the runner; no remote cleanup path exists.
    admin.dispose()


def test_roles_grants_rls_and_defaults(staging):
    admin, owner, backend, _ = staging
    allowed = {
        "vessels": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "documents": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "document_chunks": {"SELECT", "INSERT", "DELETE"},
        "auth_sessions": {"SELECT", "INSERT", "DELETE"},
        "rate_windows": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        "ai_daily_usage": {"SELECT", "INSERT", "UPDATE"},
        "alembic_version": {"SELECT"},
    }
    with admin.begin() as c:
        for role in ("maritime_backend", "maritime_migrator"):
            assert (
                c.execute(
                    text(
                        "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=:r"
                    ),
                    {"r": role},
                ).scalar()
                is False
            )
        assert not c.execute(
            text("SELECT has_schema_privilege('maritime_backend','public','CREATE')")
        ).scalar()
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM pg_auth_members WHERE member='maritime_backend'::regrole"
                )
            ).scalar()
            == 0
        )
        for table in TABLES:
            assert c.execute(
                text("SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass(:t)"),
                {"t": "public." + table},
            ).scalar()
            assert (
                c.execute(
                    text(
                        "SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid=to_regclass(:t)"
                    ),
                    {"t": "public." + table},
                ).scalar()
                == "maritime_migrator"
            )
            for role in ("maritime_backend", "anon", "authenticated"):
                for privilege in (
                    "SELECT",
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                    "TRUNCATE",
                    "REFERENCES",
                    "TRIGGER",
                ):
                    actual = c.execute(
                        text("SELECT has_table_privilege(:r,:t,:p)"),
                        {"r": role, "t": "public." + table, "p": privilege},
                    ).scalar()
                    assert actual == (
                        role == "maritime_backend" and privilege in allowed[table]
                    )
            assert (
                c.execute(
                    text(
                        "SELECT count(*) FROM pg_class c, LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a WHERE c.oid=to_regclass(:t) AND a.grantee=0"
                    ),
                    {"t": "public." + table},
                ).scalar()
                == 0
            )
        for privilege in ("SELECT", "UPDATE", "USAGE"):
            assert c.execute(
                text(
                    "SELECT has_sequence_privilege('maritime_backend','public.document_chunks_id_seq',:p)"
                ),
                {"p": privilege},
            ).scalar() == (privilege == "USAGE")
        # Even an accidental browser SELECT grant must not bypass RLS.
        c.execute(text("GRANT SELECT ON public.alembic_version TO anon, authenticated"))
        for role in ("anon", "authenticated"):
            c.execute(text(f"SET LOCAL ROLE {role}"))
            assert (
                c.execute(text("SELECT count(*) FROM public.alembic_version")).scalar()
                == 0
            )
            c.execute(text("RESET ROLE"))
        c.execute(
            text("REVOKE SELECT ON public.alembic_version FROM anon, authenticated")
        )
    with owner.begin() as c:
        c.execute(text("CREATE TABLE public.synthetic_future(id serial PRIMARY KEY)"))
        for role in ("anon", "authenticated", "maritime_backend"):
            assert not c.execute(
                text(
                    "SELECT has_table_privilege(:r,'public.synthetic_future','SELECT')"
                ),
                {"r": role},
            ).scalar()
            assert not c.execute(
                text(
                    "SELECT has_sequence_privilege(:r,'public.synthetic_future_id_seq','USAGE')"
                ),
                {"r": role},
            ).scalar()
        c.execute(text("DROP TABLE public.synthetic_future"))
    for statement in (
        "CREATE TABLE public.forbidden(id int)",
        "TRUNCATE public.documents",
        "UPDATE public.alembic_version SET version_num='0003'",
        "SET ROLE maritime_migrator",
        "ALTER TABLE public.documents DISABLE ROW LEVEL SECURITY",
    ):
        with pytest.raises(Exception):
            with backend.begin() as c:
                c.execute(text(statement))
    with backend.connect() as c:
        assert (
            c.execute(text("SELECT version_num FROM public.alembic_version")).scalar()
            == "0004"
        )


def test_restricted_backend_application_operations_and_rollback_guard(
    staging, monkeypatch
):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from test_online_mvp import (
        MemoryStorage,
        online_settings,
        GatewayAuth,
        HOST,
        sign_in,
        upload,
    )

    _, owner, _, backend_url = staging
    storage = MemoryStorage()
    monkeypatch.setattr("app.main.create_storage", lambda *a: storage)
    settings = online_settings(
        database_url=backend_url.render_as_string(hide_password=False)
    )
    app = create_app(settings)
    try:
        with TestClient(app, base_url="http://" + HOST) as client:
            client.auth = GatewayAuth()
            sign_in(client)
            response = client.post(
                "/api/vessels", json={"vessel_name": "Synthetic staging vessel"}
            )
            assert response.status_code == 201
            vessel = response.json()
            assert (
                client.patch(
                    "/api/vessels/" + vessel["id"], json={"flag": "Synthetic"}
                ).status_code
                == 200
            )
            document, _ = upload(client)
            assert client.get("/api/documents").status_code == 200
            assert client.get("/api/vessels/" + vessel["id"]).status_code == 200
            from app.services.ai_limits import AIGuard

            guard = AIGuard(app.state.engine, settings)
            guard.reserve_budget(settings.admin_username)
            guard.record_usage(
                settings.admin_username,
                settings.openai_model,
                {"input_tokens": 1, "output_tokens": 1},
            )
            assert client.get("/api/ai/usage").status_code == 200
            # Full-text generated column / sequence access runs through upload/search.
            assert (
                client.get(
                    "/api/documents/" + document["id"] + "/search",
                    params={"q": "synthetic"},
                ).status_code
                == 200
            )
            with pytest.raises(RuntimeError, match="Back up"):
                with owner.begin() as c:
                    config = Config("alembic.ini")
                    config.attributes["connection"] = c
                    command.downgrade(config, "0003")
            assert (
                client.request(
                    "DELETE", "/api/documents/" + document["id"], json={}
                ).status_code
                == 200
            )
            assert client.post("/api/auth/logout", json={}).status_code == 200
    finally:
        app.state.engine.dispose()
    restarted = create_app(settings)
    try:
        with TestClient(restarted, base_url="http://" + HOST) as client:
            client.auth = GatewayAuth()
            sign_in(client)
            assert (
                client.get("/api/vessels/" + vessel["id"]).json()["vessel_name"]
                == "Synthetic staging vessel"
            )
    finally:
        restarted.state.engine.dispose()


def test_tls_rejects_wrong_hostname_and_untrusted_ca(staging, tmp_path):
    _, _, _, url = staging
    kwargs = dict(
        host=url.host,
        port=url.port,
        dbname=url.database,
        user=url.username,
        password=url.password,
        sslmode="verify-full",
        sslrootcert=url.query["sslrootcert"],
        connect_timeout=3,
    )
    with psycopg.connect(**kwargs) as c:
        assert c.execute(
            "SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
        ).fetchone()[0]
    with pytest.raises(psycopg.OperationalError, match="does not match"):
        psycopg.connect(**(kwargs | {"host": "wrong.invalid", "hostaddr": "127.0.0.1"}))
    import subprocess

    wrong_ca = tmp_path / "untrusted.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=untrusted",
            "-keyout",
            str(tmp_path / "key"),
            "-out",
            str(wrong_ca),
        ],
        check=True,
        capture_output=True,
    )
    with pytest.raises(psycopg.OperationalError, match="certificate verify failed"):
        psycopg.connect(**(kwargs | {"sslrootcert": str(wrong_ca)}))
