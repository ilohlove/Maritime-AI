# Supabase staging database preparation

Prepared 2026-11-09 for `ilohlove/Maritime-AI`, base `feature/online-mvp-v1`.
Scope: **only** the separate `maritime-ai-staging` project and private
`maritime-ai-documents` bucket. SSL enforcement is already enabled by the operator.
Nothing here has been run against Supabase. Do not touch Crewport, the existing
Render service or Worker. AI stays disabled. All validation data is synthetic.

## Audit of migrations 0001–0004

| Revision | PostgreSQL review | Deployment/rollback behavior |
| --- | --- | --- |
| 0001 | String IDs, JSON, NUMERIC(14,3), timestamptz are supported; identifiers retain leading zeroes. No extensions needed. | Creates vessels. Downgrade drops data; use only on empty disposable databases. |
| 0002 | LargeBinary becomes BYTEA; integer chunk PK creates `document_chunks_id_seq`; FK and index supported. SQLite FTS5/triggers are correctly dialect guarded. | Drops children before parents. Does not migrate SQLite documents to PostgreSQL. |
| 0003 | Columns, floats and security tables are compatible. `window` is quoted in application SQL. | Downgrade refuses file-backed originals; its SQLite-oriented error wording also appears on PostgreSQL. |
| 0004 | Ownership/index columns, bigint counters and persisted `to_tsvector('simple'::regconfig,text)` with GIN are PostgreSQL compatible. RLS and revokes include Alembic state. | Downgrade refuses populated vessels/documents/usage; retained RLS/revokes on an empty downgrade are deliberate fail-closed behavior. |

These are versioned Alembic migrations, not individually rerunnable SQL files.
`alembic upgrade head` is repeatable because Alembic records the revision. Do not
add `IF NOT EXISTS` or `stamp head` to disguise a partial/unrecognized schema.
PostgreSQL transactional DDL in the existing env wraps upgrade execution; initial
creation and 0004 revokes commit together. The fresh dedicated database must
remain unused until provisioning and verification finish. Never stop at 0001–0003
and expose those tables. History is unchanged; head stays **0004**.

0004 alone denies a non-owner backend because no backend RLS policy exists. The
new provisioning script supplies that policy. Previous deployment documentation
also granted unnecessary DML on Alembic state and blanket sequence permissions;
it now points here. The backend does not own tables and cannot bypass RLS.
The migration owner deliberately retains PostgreSQL's owner bypass (RLS is
ENABLED, not FORCED), needed for migrations/version writes and rollback reads.
Administrators and Supabase service roles remain privileged; RLS is not a defense
against an administrator or a leaked service-role key.

## Roles and application privilege contract

| Object | `maritime_backend` privileges |
| --- | --- |
| vessels, documents, rate_windows | SELECT, INSERT, UPDATE, DELETE |
| document_chunks | SELECT, INSERT, DELETE |
| auth_sessions | SELECT, INSERT, DELETE |
| ai_daily_usage | SELECT, INSERT, UPDATE |
| alembic_version | SELECT only (startup revision check) |
| document_chunks_id_seq | USAGE only (nextval/currval); no SELECT or UPDATE/setval |
| public schema | USAGE only; no CREATE |

`maritime_migrator` is a separate LOGIN owning application objects, with public
schema USAGE/CREATE. Neither login has SUPERUSER, BYPASSRLS, CREATEDB, CREATEROLE,
REPLICATION, role inheritance, or membership in another role. No backend grant
options, TRUNCATE, REFERENCES, TRIGGER, Auth/Storage schema privileges or grants
on future tables are needed. Bootstrap permits the executing administrator's
ADMIN membership in the roles: PostgreSQL 16+ CREATEROLE may create this
membership automatically. It rejects other inbound memberships and all outbound
memberships. Do not grant these logins to `authenticator`, `anon`, or `authenticated`.

Policies target only `maritime_backend`. They allow the trusted server to operate
all application rows; FastAPI supplies owner authorization. This is **not database
per-tenant isolation**. A stolen backend credential compromises application data.
Database CONNECT/TEMP and existing platform public function/schema privileges
may be inherited from PUBLIC. This procedure does not globally revoke managed
platform capabilities; audit them before treating the role as isolated from all
other Supabase services. The guarantees here cover the listed application objects.

## Manual execution procedure (operator only)

Use a trusted workstation with the locked Python dependencies, PostgreSQL client
(`psql`, `pg_dump`) and the public certificate bundle for the **pooler** endpoint.
Keep passwords in a password manager and a private mode-0600 PGPASSFILE (or an
interactive prompt), never command arguments, tracked files, chat, shell history
or SQL script variables. Never enable shell tracing or SQL statement/password
logging during password setup. `psql \password` avoids plaintext SQL history but
requires protecting administrative/server logs too.

1. In the dashboard verify project reference/name **maritime-ai-staging**, private
   bucket **maritime-ai-documents**, SSL enforcement, and port **5432 Session
   Pooler**. Confirm `public` contains no user tables or application data. If it
   does, stop and inventory/back up first; do not use this fresh-install procedure.
   Check exposed schemas, existing policies, role/default grants and membership.
   Use only this new project. An existing conflicting role must be manually
   reviewed; the scripts fail on unsafe attributes/membership rather than silently
   remove privileges from unknown users.
2. Obtain the exact Session Pooler DNS hostname, project reference, database name
   (normally `postgres`) and trusted CA chain for that hostname from the dashboard
   and provider documentation. A direct database CA is not necessarily the pooler
   CA. Inspect the presented chain/issuer without accepting an untrusted chain;
   use the OS public CA bundle if it is the appropriate trust anchor, or mount the
   verified provider bundle. Do not blindly trust a certificate downloaded from
   the endpoint being tested. No `sslmode=require`, disabled verification, IP
   hostname substitution, or fallback to another project.
3. Set non-secret libpq variables in the operator shell:

   ```sh
   export PGHOST=EXACT_SESSION_POOLER_DNS_HOST
   export PGPORT=5432 PGDATABASE=postgres PGSSLMODE=verify-full
   export PGSSLROOTCERT=/absolute/path/to/trusted-pooler-ca-bundle.pem
   export PGUSER=postgres.PROJECT_REF
   # Set PGPASSFILE to an untracked private file outside the checkout, if used.
   psql -X -v ON_ERROR_STOP=1 -f scripts/supabase/01_roles.sql
   psql -X -v ON_ERROR_STOP=1
   ```

   In the interactive admin psql session run `\password maritime_migrator` and
   `\password maritime_backend`, using different generated secrets; then `\q`.
   Newly created roles have no password until this step. Bootstrap sets role
   defaults and revokes PUBLIC schema CREATE in this **dedicated** staging project.
   The next owner-only step removes default grants. Managed ownership/event-trigger differences
   can still add grants; later verification is mandatory. Do not bootstrap as the
   backend or grant SUPERUSER/BYPASSRLS to resolve permission errors.
4. Reconnect using `PGUSER=maritime_migrator.PROJECT_REF` and the migrator's password
   entry. The SQL role must be `maritime_migrator`, without the routing suffix:

   ```sh
   export PGUSER=maritime_migrator.PROJECT_REF
   python scripts/supabase/validate_connection.py --expected-role maritime_migrator
   psql -X -v ON_ERROR_STOP=1 -c 'SELECT current_user, current_database(), current_schema();'
   ```

   Still as this login, run the defaults script **before** migrating:

   ```sh
   psql -X -v ON_ERROR_STOP=1 -f scripts/supabase/01b_migration_defaults.sql
   ```

   Managed CREATEROLE administrators do not necessarily inherit or have SET ROLE
   access to newly created roles, so default privileges must be configured by the
   actual migration owner. Use this login, not `SET ROLE` inside a pooled admin
   session, for migrations.
   libpq environment supplies credentials to psycopg. With the runtime online
   environment **unloaded**, from a fresh operator shell retain PG* variables and
   run the following from `backend` (the credential-free URL is literal):

   ```sh
   export MARITIME_ENV=development MARITIME_ONLINE_MVP_MODE=false
   export MARITIME_DATABASE_URL='postgresql+psycopg:///?sslmode=verify-full'
   alembic current
   alembic upgrade head --sql > /tmp/maritime-staging-reviewed.sql
   # Review all DDL; confirm only the application objects listed above.
   alembic upgrade head
   alembic current
   alembic upgrade head
   ```

   For a fresh project, current is initially empty and afterward exactly `0004`;
   the second upgrade must be a no-op. Offline `--sql` does not connect. PGUSER,
   PGPASSFILE and the verified TLS libpq variables are inherited; there is no
   migration password in a URL. Do not load production gateway/storage/AI secrets
   just to run Alembic. For an unexpected revision or error, stop, inspect the
   transaction outcome and schema; do not stamp, drop or retry destructively.
5. From repository root, still as the migrator, run:

   ```sh
   psql -X -v ON_ERROR_STOP=1 -f scripts/supabase/02_application_access.sql
   ```

   It is transactional and repeatable, checks expected owner/head and refuses
   unknown policies. It revokes/rebuilds explicit application grants and policy,
   plus the one known sequence. No managed auth/storage tables are changed.
6. Reconnect as the staging administrator and run the read-only assertions:

   ```sh
   export PGUSER=postgres.PROJECT_REF
   psql -X -v ON_ERROR_STOP=1 -f scripts/supabase/03_verify.sql
   export PGUSER=maritime_backend.PROJECT_REF
   python scripts/supabase/validate_connection.py --expected-role maritime_backend
   ```

   Inspect *all* memberships and effective grants, including unexpected function
   EXECUTE privileges and managed event-trigger grants. `03_verify.sql` proves
   exact listed object permissions, owner/RLS/policy shape and role flags, not
   every Supabase-managed capability. Do not run Alembic as this backend role.
7. Complete [the security checklist](SUPABASE_STAGING_SECURITY_CHECKLIST.md).
   Store only the backend credential in any future separately authorized backend
   configuration, using `deploy/online-mvp.env.example`. Set its private bucket
   name to `maritime-ai-documents`. Do not configure or restart an existing service.

## Session Pooler and TLS compatibility

Session mode uses port 5432 (transaction mode commonly uses 6543). Username is
`<SQL_ROLE>.<PROJECT_REF>`, e.g. `maritime_backend.PROJECT_REF`; the SQL role itself
is simply `maritime_backend`. Password is that role's own password, not the
project admin password or a Supabase API key. Obtain the hostname from Connect;
never guess it from the project URL. Supavisor custom-role/password authentication
must be checked in the actual project; a local PostgreSQL test cannot certify it.

The existing SQLAlchemy engine opens at most two backend connections, disables
prepared statements and sets timeouts at session creation. Migrations use
NullPool; allow one extra migrator/admin connection and budget against the actual
Free project limits. Keep a single backend worker/replica. No transaction-pooler
compatibility is claimed by these session-specific checks.

`sslmode=verify-full` validates CA chain **and DNS hostname**. Explicit readable
`sslrootcert` avoids relying on a user's implicit ~/.postgresql root file. Keep
CA material mounted when the application starts; it is public but must have
integrity protection. A Session Pooler has two TLS hops: client verification
covers client→pooler, while `pg_stat_ssl` reports pooler→database. Seeing `ssl=true`
alone does not prove client certificate/hostname verification. The probe enforces
client verify-full and checks expected SQL identity and upstream SSL. Check the
provider's upstream TLS assurance independently; do not weaken client verification.

## Free plan assessment and readiness limits

No known PostgreSQL feature in 0001–0004 needs a paid extension, superuser or
paid plan: standard roles, RLS, generated columns and GIN are sufficient. Session
Pooler, private Storage and S3-compatible access are the intended architecture,
but current project eligibility and account quotas were **not remotely checked**.
Verify their availability in the dashboard before declaring end-to-end readiness.

Free projects can pause and have limited database/storage size, egress and pooled
connections. Do not assume production availability, network restrictions, managed
backup downloads, PITR or object version history are included. An architecture
requiring always-on service, guaranteed restore points or paid-only network
controls is blocked on Free; this staging design needs operator backups and
tolerates pauses. If custom-role pooler authentication, trusted pooler TLS or S3
credentials are unavailable in this project, stop: DB preparation does not make
the full MVP deployable. Do not purchase IPv4, upgrade plans or substitute public
storage to work around it. OpenAI remains off and is outside Free-plan validation.

Provider references for the operator to recheck (not live-verified in this task):
[connections](https://supabase.com/docs/guides/database/connecting-to-postgres),
[roles](https://supabase.com/docs/guides/database/postgres/roles),
[SSL enforcement](https://supabase.com/docs/guides/platform/ssl-enforcement),
[Storage S3](https://supabase.com/docs/guides/storage/s3/compatibility),
[backups](https://supabase.com/docs/guides/platform/backups),
[pricing](https://supabase.com/pricing).

## Local validation and rollback

```sh
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
python scripts/test_postgres.py
# The runner uses only the local Docker socket, ephemeral PostgreSQL 17/TLS,
# generated passwords/certificates, and synthetic data; cleanup runs on failure.
cd backend && python -m pytest -q
cd ../frontend && npm test && npm run build
```

Local results on 2026-11-09 (Linux): full backend suite with disposable PostgreSQL
`python scripts/test_postgres.py -q`: **221 passed**; default integration run:
**70 passed**. Backend without the PostgreSQL URL: **203 passed, 18 skipped**
(the full PostgreSQL run above includes those cases). Frontend: **31 passed** and
production build passed. Chromium with the isolated synthetic SDK harness:
**5 passed, 1 skipped** (optional disposable UI case). The SDK used only a local
mock transport; no OpenAI request occurred. One upstream TestClient deprecation
warning remains. No Windows or provider integration validation is claimed.

The local runner includes the staging suite by default and is already called by
PostgreSQL CI. Tests exercise a non-superuser CREATEROLE administrator, real
owner/runtime logins, migration repeat/empty round trip, transaction rollback,
populated downgrade refusal, defaults, RLS, effective ACLs, denied DDL/escalation,
restricted HTTP operations and certificate/hostname rejection. It models default
Supabase browser grants but not Supavisor, PostgREST, managed triggers or Storage.

Before any populated upgrade, stop writes and take an encrypted `pg_dump -Fc`
with an authorized operator credential plus a matching private object copy and
checksums/revision manifest. Restore both into disposable local resources and
verify ownership/grants, document hashes and application behavior. Do not use the
SQLite-only backup script. Document RPO/RTO and retention. To abandon an initial
empty migration, retain error/schema evidence and have the operator review a
fresh-project retry. For populated databases restore a matching database/object
snapshot; never downgrade 0004 over live rows. Lock out the backend if needed with
an administrator's `ALTER ROLE maritime_backend NOLOGIN`, then terminate/recycle
existing backend/pooler sessions separately; NOLOGIN alone does not disconnect
sessions. Keep AI disabled and revoke restored auth sessions. Dropping roles,
projects, data or buckets is a separate destructive action.
