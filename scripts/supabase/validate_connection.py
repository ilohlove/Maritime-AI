"""Operator-only TLS connection probe. Never prints a DSN, secret or DB error."""

import argparse
import ipaddress
import os
from pathlib import Path

import psycopg


def connection_parameters(env):
    host = env.get("PGHOST", "")
    if not host or any(c in host for c in "/, ="):
        raise ValueError("PGHOST must be one DNS hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Use the certificate DNS hostname, not an IP address")
    cert = Path(env.get("PGSSLROOTCERT", ""))
    if not cert.is_file():
        raise ValueError("PGSSLROOTCERT must point to a readable trusted CA bundle")
    if env.get("PGSSLMODE") != "verify-full" or env.get("PGPORT") != "5432":
        raise ValueError("Require PGSSLMODE=verify-full and Session Pooler PGPORT=5432")
    if not env.get("PGUSER") or not env.get("PGDATABASE"):
        raise ValueError("PGUSER and PGDATABASE are required")
    return dict(
        host=host,
        port=5432,
        user=env["PGUSER"],
        dbname=env["PGDATABASE"],
        sslmode="verify-full",
        sslrootcert=str(cert),
        connect_timeout=10,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-role",
        choices=["maritime_backend", "maritime_migrator"],
        required=True,
    )
    args = parser.parse_args()
    try:
        parameters = connection_parameters(os.environ)
        with psycopg.connect(**parameters) as connection:
            role, ssl, version = connection.execute(
                "SELECT current_user, ssl, version FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
            ).fetchone()
            if role != args.expected_role or not ssl:
                raise ValueError("Unexpected SQL role or unencrypted upstream session")
            print(
                f"PASS: expected SQL role; verify-full connection; upstream TLS {version}"
            )
    except (ValueError, OSError, psycopg.Error):
        print(
            "FAIL: check role-specific username, password, CA chain, DNS hostname and TLS settings locally"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
