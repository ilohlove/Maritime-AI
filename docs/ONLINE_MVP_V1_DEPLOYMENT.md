# Online MVP V1 deployment and rollback

Prepared 2026-11-07. **No deployment or external resource creation was performed.**
Leave the existing Render service, Worker, deployment branch, secrets and
`deploy/gateway/wrangler.jsonc` unchanged. Use separately authorized staging
resources and a new bucket/database; do not repurpose disposable storage.

## Required user interventions before external actions

1. Review current provider terms and account eligibility. Verify Supabase Free
   database capacity, S3 protocol availability, private buckets, API/egress quotas,
   pause policy, connection limits and backup availability. Confirm Render Free
   runtime/sleep/startup limits and Cloudflare Workers request/CPU quotas.
2. Explicitly authorize creation of separate staging resources after their
   costs are known. Account creation, OAuth, payment details and external secret
   entry belong in the providers' interfaces; never paste secrets into chat.
3. Provision PostgreSQL, a private object bucket and backend-only credentials.
   Obtain exact pooler hostname, database username, region and S3 endpoint from
   that project's dashboard. An ordinary Supabase anon key is not an S3 key.
4. Configure secrets in the **new backend** and a new gateway secret in the
   **new Worker**. Do not reuse the live gateway secret.
5. Complete the staging checks below before authorizing any production cutover.
6. Restore valid GitHub repository authentication to publish the prepared PR.
   `gh auth status` reported invalid GH_TOKEN in this session; no remote PR was
   created. Use environment credential settings or `gh auth login`, not chat.

## Configuration

The complete backend template is [online-mvp.env.example](../deploy/online-mvp.env.example).
These are backend environment variables, not Vite variables:

| Variables | Requirement |
| --- | --- |
| `MARITIME_ENV=production`, `MARITIME_ONLINE_MVP_MODE=true` | Explicit online profile; disposable flag false; omit disposable ACK/root |
| `MARITIME_DATABASE_URL` | PostgreSQL/psycopg URL; URL-encoded credentials; `sslmode=verify-full`; provider CA via `sslrootcert=system` or mounted public CA file |
| `MARITIME_STORAGE_BACKEND=s3`, `MARITIME_STORAGE_PERSISTENT=true` | Mandatory; local paths cannot substitute |
| `MARITIME_S3_ENDPOINT`, `_REGION`, `_BUCKET` | Exact HTTPS S3-compatible endpoint, region and private bucket |
| `MARITIME_S3_ACCESS_KEY`, `_SECRET_KEY`, `_PRIVATE_BUCKET=true` | Backend secrets and operator privacy acknowledgement |
| `MARITIME_HTTPS_TRANSPORT=signed-gateway`, `MARITIME_GATEWAY_SECRET` | Independent 64-character lowercase hex secret shared with only the new Worker |
| `MARITIME_PASSWORD_HASH`, `MARITIME_ADMIN_USERNAME` | Scrypt hash generated interactively by `python scripts/hash_password.py`; stable single-owner username |
| `MARITIME_TRUSTED_HOSTS`, `MARITIME_ALLOWED_ORIGINS` | New Render hostname and new HTTPS Worker origin, no wildcards/paths |
| `MARITIME_AUTH_TRANSPORT=bearer`, `MARITIME_SESSION_SECONDS` | Session duration 300–86400 seconds; default 3600 |
| `MARITIME_BIND_HOST=0.0.0.0`, `WEB_CONCURRENCY=1` | Render listener, one worker and one replica; platform supplies `PORT` |
| `MARITIME_TRUSTED_PROXY_IPS` | Empty; do not trust forwarded headers or `FORWARDED_ALLOW_IPS=*` |
| `MARITIME_LOGIN_LIMIT`, `MARITIME_UPLOAD_RATE_LIMIT`, `MARITIME_MAX_DOCUMENTS` | Defaults 5 login attempts/minute/IP, 3 uploads/minute, 20 documents/owner; global document cap 100 |
| `MARITIME_AI_ENABLED=false`, `OPENAI_API_KEY` | Off by default; key may be absent. Activation needs separate authorization |
| `OPENAI_MODEL`, `OPENAI_MODELS` | Exactly one priced structured-output model in online mode |
| `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES=0` | Timeout 0–120 seconds; no automatic retries |
| `MARITIME_AI_RATE_LIMIT`, `_CONCURRENCY`, `_DAILY_TOKEN_BUDGET`, `_MAX_INPUT_TOKENS`, `_OUTPUT_TOKENS`, `_TRANSLATION_TOKENS` | Default 5/minute, 1 active, 100000/day, 20000/input call, 2000 answer output, 512 translation output |
| `MARITIME_AI_INPUT_USD_PER_MILLION`, `_OUTPUT_USD_PER_MILLION` | Verify configured price estimates for selected model before activation |

Frontend: build with relative `/api` (unset `VITE_API_BASE_URL`) and bearer auth.
No database, storage, password, gateway or OpenAI secret may have a `VITE_` prefix.
The Worker needs only the two new HTTPS origins, `MARITIME_ONLINE_MVP_MODE=true`,
`ASSETS`, and its new gateway secret. Review the [separate Worker example](../deploy/gateway/wrangler.online-mvp.example.jsonc).
It is intentionally separate from the existing deployment configuration.

## PostgreSQL migration and access

Use a fresh database/schema and a migration owner, not the restricted runtime
role. Review generated DDL and take an encrypted backup before upgrading any
populated database. No SQLite-to-PostgreSQL conversion is automatic.

```sh
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
# In a secure shell, load the new backend configuration with migration DB credentials.
cd backend
alembic current
alembic upgrade head
alembic current
```

Expected head: `0004`. Run migrations once explicitly; the online start command
never invokes Alembic. Existing local SQLite upgrades retain BLOB/file originals,
FTS and profile data. Never copy disposable sessions into the persistent service.
Online startup refuses unowned/legacy rows. Re-import approved originals and
create profiles through authenticated endpoints; any bulk import/ownership
assignment needs an audited migration and separate data-loss review.

Supabase's public-schema Data API is a separate ingress. The PostgreSQL migration
enables RLS on all application tables, revokes PUBLIC and existing anon /
authenticated grants, and creates no public policies. With provider SQL tooling,
create a backend-only login with a generated secret (do not grant it to anon /
authenticated), then run the following **as the migration owner**, adapting schema
names. Creating roles/grants is an external action and has not been executed.

```sql
-- Role maritime_backend must first exist with LOGIN and an operator-set password.
GRANT USAGE ON SCHEMA public TO maritime_backend;
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['vessels','documents','document_chunks','auth_sessions',
                           'rate_windows','ai_daily_usage','alembic_version'] LOOP
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO maritime_backend', t);
    EXECUTE format('CREATE POLICY backend_only ON public.%I TO maritime_backend USING (true) WITH CHECK (true)', t);
  END LOOP;
END $$;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO maritime_backend;
```

Do not expose backend-role tokens through Supabase Auth or the browser. FastAPI
checks owner IDs; these policies intentionally permit the trusted backend to
operate its private tables, while browser roles have no access. Runtime needs no
schema CREATE, migration ownership, superuser or BYPASSRLS privileges. Store a
separate migration credential outside the runtime service. Verify actual provider
role/pooler username syntax in the dashboard.

Use Supabase's session pooler where direct IPv6 is unavailable. The app pool
opens at most two runtime connections; allow a separate migration/admin
connection. Query live provider connection limits and account for other clients.
Do not size pools from unverified free-plan assumptions. Direct connections also
work if reachable. Prepared statements are disabled. Before considering a
transaction pooler, validate its TLS/role behavior and set role-level
`statement_timeout='10s'`, `lock_timeout='5s'`; session SET behavior alone is
insufficient for transaction pooling.

## Authorized staging deployment sequence

1. Verify provider privacy, TLS and the backend role using synthetic data only.
   Confirm public/anon/authenticated roles cannot query tables or read objects.
2. Run the checks in [test report](ONLINE_MVP_V1_TEST_REPORT.md). Build frontend
   with `npm ci && npm test && npm run build` inside `frontend`.
3. Create a separate Render service at `feature/online-mvp-v1`, automatic deploy
   disabled, using Python 3.12. Install from the locked requirements and editable
   backend as above. Set start command `python scripts/start_backend.py`.
   Set health path `/api/health` only if the platform can provide a valid gateway
   proof: direct unsigned health requests intentionally receive 401. Do not add
   an unsigned health exception; omit the optional HTTP health path/use platform
   port readiness if supported, and test the deployment lifecycle explicitly.
4. Apply configuration and run the migration through an authorized secure shell
   or local operator connection. Free-host shell/predeploy features may be
   unavailable; use a trusted operator machine with provider network access.
5. Create a separate Worker from the online example and attach built assets.
   Configure its matching gateway secret in the provider secret manager. Do not
   use the existing default Wrangler configuration or live Worker name.
6. Keep AI disabled. Test sign-in/out, exact profile create/edit/restart, real
   synthetic PDF upload/restart, local search, evidence inspection, download,
   deletion, interrupted-upload cleanup and missing-storage failure. Recheck
   unsigned origin denial, expired/replayed signatures, Host/Origin rejection,
   session revocation and anonymous Supabase REST/storage denial.
7. Measure free-instance RSS/CPU, request-body signing CPU, parser resource limits,
   cold-start latency and storage startup probes. The local tests do not certify
   Workers Free CPU or Render Free memory behavior. Reduce limits or select a
   separately authorized plan if measurements exceed provider allowances.
8. Only after explicit spending authorization: set a project-specific OpenAI
   backend key, verify model prices and external processing terms, choose quota,
   and set `MARITIME_AI_ENABLED=true`. Obtain fresh in-app consent for each real
   question. Test a small approved synthetic request and reconcile actual billing.

No cutover to existing public URLs is authorized by this document.

## Recovery, backup and rollback

Keep PostgreSQL backups and object snapshots together with a manifest of object
keys, SHA-256, sizes, ownership and schema/application revisions. Encrypt backups,
restrict operators, test restore and define retention/RPO/RTO. Free-tier backups,
PITR and object versions must be verified; do not assume they are provided.
For a consistent manual backup stop new writes/inference, take `pg_dump` and a
private bucket copy, then resume. Never log dump contents or secrets. The existing
`scripts/backup.py` is SQLite-only and must not be used for online backups.

Pending/deleting records remain visible in the library. After storage recovers,
retry Delete selected document, then re-upload as needed. A restart never makes
an incomplete document available for answering. Missing ready originals prevent
startup: restore the correct bucket/objects from the matching backup. Do not
remove metadata to hide a missing object. Compare checksum on private download.

For an unsuccessful staging rollout disable inference, stop the new backend /
Worker and retain their data for diagnosis. The existing deployed application
continues unchanged. For persistent application rollback, stop writes, restore a
matching tested database and object snapshot into separately named resources,
revoke restored sessions, and switch only the separately authorized staging
configuration. Preserve the current day's quota/reservations or keep inference
disabled until UTC reset: restoring an earlier ledger can permit repeat spending.
Do not downgrade populated migration 0004, run the disposable launcher on online
data, or drop/overwrite production data. Keep old resources until restore has
been verified and deletion is separately authorized.
