# Staging security and rollback checklist

Prepared 2026-11-09. Local validation does **not** mark external checks complete.
Record date/operator/project reference and evidence privately, without credentials
or vessel/document contents. All remote actions below are manual and must target
only `maritime-ai-staging`. No staging or production services were deployed.

## Before migration

- [ ] Confirm the project name AND unique reference in the dashboard; Crewport and
  existing Render/Worker configurations remain untouched.
- [ ] Confirm no existing application data/tables; stop for inventory/backup if any
  exist. Confirm SSL enforcement and the Session Pooler hostname/5432.
- [ ] Confirm Free-plan custom-role session authentication, private Storage and
  S3 credentials are available; record actual size/connection/egress quotas and
  pause/backup restrictions. No paid feature, upgrade or IPv4 add-on enabled.
- [ ] Trust a verified CA bundle for the exact pooler DNS hostname. No TLS bypass
  or IP hostname substitution. Protect bundle integrity and private secret files.
- [ ] Review the 0001–0004 audit and generated SQL in
  [setup](SUPABASE_STAGING_SETUP.md); head must remain 0004.
- [ ] Review default grants, managed DDL event triggers, exposed API schemas, role
  memberships and unexpected SECURITY DEFINER function access. Do not assume
  the local PostgreSQL model reproduces provider-specific grants.

## Provisioning and SQL access

- [ ] Run `01_roles.sql` as the separate project's administrator; set distinct
  role passwords via interactive `\password`; retain migrator secrets only with
  operators. Neither credential is present in code, logs or frontend variables.
- [ ] Migrator probe passes using `maritime_migrator.PROJECT_REF`; SQL
  `current_user` is `maritime_migrator`; CA/hostname verification is enabled.
- [ ] Run `01b_migration_defaults.sql` as migrator before Alembic; confirm both
  global and schema-specific default grants are cleared for browser/runtime roles.
- [ ] Run Alembic as migrator: empty → 0004, subsequent upgrade is a no-op. No
  partial schema, `stamp` workaround or SQLite data import.
- [ ] Run `02_application_access.sql` as migrator; run `03_verify.sql` as admin.
  Save success/revision evidence. RLS enabled on all seven application tables;
  exact backend-only policy present. Owner bypass is intentional and restricted
  to migration operators. Runtime is neither table owner nor a privileged role.
- [ ] Backend probe passes with its own password and suffixed pooler username.
  No SUPERUSER, BYPASSRLS, CREATEDB, CREATEROLE, replication or role memberships;
  no schema CREATE, grant options or table DDL privileges. One sequence has USAGE
  only; Alembic state is SELECT only. No grants on future application objects.
- [ ] Reconnect with backend credentials and verify SELECT on Alembic state.
  In separate transactions, CREATE TABLE public, TRUNCATE application tables,
  UPDATE alembic_version, SET ROLE maritime_migrator and ALTER TABLE/DISABLE RLS
  must fail. Never test destructive success paths on valuable data.
- [ ] Review effective permissions beyond these application objects: PUBLIC
  database TEMP/CONNECT, other schemas/functions and privileged service keys.
  Standard Supabase service-role access is not constrained by browser-role RLS.

## Data API denial (manual, synthetic data only)

- [ ] Confirm whether the Data API is enabled. Disable it in this separate project
  if unused; still verify database ACL/RLS. If enabled, inspect exposed schemas.
- [ ] With no API key and no Authorization, attempt REST reads on each of
  `vessels`, `documents`, `document_chunks`, `auth_sessions`, `rate_windows`,
  `ai_daily_usage`, `alembic_version`. Expect gateway denial, no rows/metadata.
- [ ] Repeat using this staging project's public publishable/anon key only;
  ensure no service-role key is used. Require permission denial/hidden relation,
  not merely an empty successful response on an empty database.
- [ ] If staging Supabase Auth is enabled, repeat with a synthetic authenticated
  user's genuine JWT (not the app's bearer token). Without this test authenticated
  API denial remains unverified; SQL catalog checks alone are not end-to-end.
- [ ] Check POST/PATCH/DELETE against harmless synthetic target IDs for both anon
  and authenticated roles; every operation must be denied and no mutation occur.
  Never send real application data or session digests to the Data API.
- [ ] Verify an accidental SELECT grant still yields no rows under RLS in local
  tests; do not deliberately grant browser access on Supabase to perform this.
- [ ] Confirm no exposed RPC/security-definer function can return application
  data, bypass RLS or assume the backend role. No backend role JWT/membership is
  issued through Supabase Auth; application auth remains enforced by FastAPI.

## Private bucket (manual; database role grants do not configure Storage)

- [ ] Bucket `maritime-ai-documents` remains private; inspect storage.objects
  policies for broad PUBLIC/anon/authenticated access to this bucket. A private
  flag alone does not cancel a permissive authenticated storage policy.
- [ ] Through the authorized operator path, upload one tiny synthetic sentinel
  under a unique synthetic key and retain its checksum.
- [ ] Attempt its public-object URL without credentials; expect 4xx and no bytes.
  A missing/random object is not sufficient proof; use the known sentinel.
- [ ] With no credentials, then public anon key, then a synthetic authenticated
  JWT if available, verify download/list/upload/overwrite/delete are denied.
  Require explicit denial; inspect logs and policies if an empty list is returned.
- [ ] Confirm backend-only S3 credentials work for put/get/head/delete of the
  sentinel with TLS verification, expected checksum and no public URL exposure.
  Treat S3 keys as privileged credentials; inspect provider key scoping and keep
  them out of clients/logs. Do not grant SQL storage schema access to the backend.
- [ ] Remove the sentinel through the authorized operator path. Verify no signed
  download URLs or service-role keys leaked. Do not modify other buckets.

## Rollback and final gate

- [ ] Define owner/operator access, RPO/RTO, encrypted backup location and retention;
  Free managed backups/PITR/object versions must not be assumed available.
- [ ] Before populated migration, stop writers; take matching database/object
  backups and a schema/app revision/checksum manifest. Test restore locally,
  restoring owners/grants as needed; verify data and originals agree.
- [ ] Retain prior application revision. Do not downgrade populated 0004; use a
  matching restored snapshot. Keep AI off and invalidate restored sessions.
- [ ] Document runtime credential rotation and emergency NOLOGIN + active session
  termination/pooler recycling; retain protected migration access for recovery.
- [ ] Re-run local tests and SQL assertions after any permission/schema change.
- [ ] Mark ready for a separately authorized staging startup only after all
  relevant remote checks above pass. Missing external evidence is a pending gate,
  never a reason to disable verification or silently use a paid feature.

Local evidence: see the implementation PR/test report. No external item is checked
by this document. Deployment, production cutover and AI activation remain outside
this task.
