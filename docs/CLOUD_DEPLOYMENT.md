# Task 02A — cloud preparation, security and operations

This branch prepares deployment; it does not deploy, publish Pages, create cloud
resources or merge another branch. The private MVP has one owner and one backend
worker/replica. Do not treat it as a multi-user or multi-tenant service.

## Authentication decision

All backend paths require authentication except `GET /api/health`, login and CORS
preflight. OpenAPI/docs are disabled. A missing development password configuration
leaves data endpoints locked; production refuses missing password/OpenAI secrets.

Generate a salted scrypt hash (`N=16384,r=8,p=5`) using the active backend venv:

```sh
python scripts/hash_password.py
```

The password is read without echo; put the resulting **hash** in the backend
secret store as `MARITIME_PASSWORD_HASH`, never in Git or Vite. Hashes are also
sensitive because they permit offline password guessing. No default production
password, signup, password reset endpoint, JWT or third-party identity service is
introduced. Use a unique password-manager-generated password/passphrase. Set `MARITIME_ADMIN_USERNAME` (default `admin`). Password rotation or
changing the username invalidates existing sessions after backend restart.

Default **bearer** transport suits GitHub Pages plus a different backend site.
Login returns a random 256-bit opaque token; only its SHA-256 digest, absolute
expiry, owner ID, credential-version digest and CSRF digest are stored in SQLite.
The frontend holds the token in module memory only, sends it in `Authorization`,
and never persists it in URLs/localStorage/sessionStorage. Refresh/close requires
login again. Server expiry is authoritative; UI timers and 401 handling remove
private components and session state. Logout revokes the server session for subsequent requests; in-flight work may finish and remains counted. A failed
logout is shown for retry rather than falsely claiming revocation.

This avoids third-party cookie dependence on mobile browsers. The trade-off is
login after refresh and bearer-token exposure if the frontend suffers XSS. The
build supplies a restrictive CSP meta tag; no external scripts are required.
GitHub Pages cannot supply all desired security headers. Every repository/app on
`https://ilohlove.github.io` shares the same origin and must be trusted: CORS cannot
restrict access to `/Maritime-AI/`. Prefer a dedicated custom domain when stronger
frontend isolation is needed. Never place auth/OpenAI secrets in a `VITE_*` variable.

Optional **cookie** transport is for a same-origin frontend/reverse-proxy setup,
not cross-site GitHub Pages. Set backend `MARITIME_AUTH_TRANSPORT=cookie` and
frontend `VITE_AUTH_TRANSPORT=cookie`. The `__Host-maritime_session` cookie is
HttpOnly, Secure, SameSite=Strict, Path=/ with no Domain. Login returns a separate
CSRF token; unsafe cookie-authenticated requests require both an allowed Origin
and matching `X-CSRF-Token`. Production rejects cookie mode with a frontend host
outside the trusted backend hosts. JSON-only writes and explicit origins protect
login against browser form/CSRF submissions. Cookie mode also requires re-login
after refresh so the frontend can reacquire its in-memory CSRF token.

Login attempts (successful or failed) are limited per client IP and globally in
persistent SQLite minute windows. IP values are hashed in counters. Verification
has one CPU/memory slot. Limits can deny the owner during an attack; add ingress
rate limiting/WAF before exposure. This MVP has no MFA, recovery UI or public team
accounts. New users/tenancy require ownership/access-control schema work first.

## Backend hosting prerequisites and startup

Use Python 3.11+, writable durable local/block storage compatible with SQLite
locking, one worker/replica, HTTPS ingress and an explicit public DNS hostname.
Do not use ephemeral container filesystems, horizontally replicated SQLite files
or an unvalidated network filesystem. Size RAM/CPU for PDF extraction, scrypt and
bounded JSON uploads; PDF extraction remains in-process, not a resource sandbox.
The ingress must impose body/connection/idle-time limits as well.

Install from repository root, using a virtual environment:

```sh
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
```

Use [deploy/backend.env.example](../deploy/backend.env.example) as a reference,
replacing placeholders in the host's environment/secret settings. The backend
does **not** automatically load `.env` files. Provision the data directories with
owner-only access before migration, for example `/var/lib/maritime/originals` and
the parent of `/var/lib/maritime/maritime.db`. Keep these outside the checkout.
The cloud ingress and durable volumes must be configured by the operator later.

Run migration as a separate, exclusive release step with the **same** storage and
secret environment as the server (back up and stop writers first):

```sh
cd backend
python -m alembic upgrade head
```

Then start from repository root:

```sh
python scripts/start_backend.py
```

This enforces one worker, defaults to loopback, and does not run migrations,
reload/debug servers or publish anything. A hosting platform that requires
`0.0.0.0` may set `MARITIME_BIND_HOST` only after securing its ingress/network.
`PORT` defaults to 8000. The process must not be internet-reachable around the
TLS ingress. `GET /api/health` returns only `{"status":"ok"}` and needs no login,
but production still requires HTTPS (or HTTPS scheme from the trusted proxy).
Startup checks schema revision 0003, FTS5, session storage, referenced original
files and writable storage. Missing migrations/volumes fail startup rather than
creating tables automatically. Do not race migrations across instances.

Configure `MARITIME_TRUSTED_PROXY_IPS` with the actual ingress IPs/CIDRs. The
launcher rejects wildcard/all-address trust and production with no explicit
proxy configuration. It passes those addresses to Uvicorn, which alone interprets
forwarded headers from trusted peers; the app never trusts arbitrary forwarded
headers itself. The proxy must replace client-supplied forwarded headers and
preserve/validate the intended Host. Do not guess broad trusted IP ranges. For
local development the launcher disables forwarded-header trust by default.

Production rejects HTTP at the application boundary, requires explicit HTTPS
CORS origins and backend trusted hosts, and returns HSTS, no-store, nosniff and
no-referrer headers. CORS permits Authorization/CSRF headers and credentials only
for exact origins, never wildcard origins. `MARITIME_ALLOWED_ORIGINS` should be
`https://ilohlove.github.io` for Pages; no repository path or trailing slash.

## Backend environment reference

| Variable | Default / production requirement |
| --- | --- |
| `MARITIME_ENV` | `development`; set `production` on a cloud host |
| `MARITIME_ADMIN_USERNAME` | `admin`, 1–100 characters, single owner |
| `MARITIME_PASSWORD_HASH` | Secret, required in production; generated scrypt hash |
| `MARITIME_AUTH_TRANSPORT` | `bearer`; optional `cookie` for same-origin hosting |
| `MARITIME_SESSION_SECONDS` | 3600; range 300–86400, absolute expiry |
| `MARITIME_ALLOWED_ORIGINS` | Local dev origins; production requires explicit HTTPS origins |
| `MARITIME_TRUSTED_HOSTS` | Local dev hosts; production requires real backend domains, no wildcard/ports |
| `MARITIME_DATABASE_URL` | SQLite absolute file URL; default derives from `MARITIME_DATA_DIR` |
| `MARITIME_DATA_DIR` | Default home `.maritime-ai`; prefer explicit mounted cloud path |
| `MARITIME_DOCUMENTS_DIR` | Default sibling `documents/`; explicit absolute path required in production |
| `MARITIME_STORAGE_PERSISTENT` | `false`; production requires literal `true` after verifying actual volumes |
| `MARITIME_LOGIN_LIMIT` | 5/IP/minute; global limit is six times this, max setting 100 |
| `MARITIME_AI_RATE_LIMIT` | 5/owner/minute; max setting 100 |
| `MARITIME_AI_CONCURRENCY` | 1 active AI workflow; maximum setting 8, single process only |
| `MARITIME_AI_DAILY_TOKEN_BUDGET` | 100000 reserved tokens/owner/UTC day; positive, max 100000000 |
| `MARITIME_AI_MAX_INPUT_TOKENS` | 20000 conservative tokens/call; positive, max 100000 |
| `MARITIME_AI_OUTPUT_TOKENS` | 2000 completion tokens for generation; positive, max 8000 |
| `MARITIME_AI_TRANSLATION_TOKENS` | 512 completion tokens for translation; positive, max 2000 |
| `OPENAI_API_KEY` | Backend secret; production requires nonempty, never sent to frontend |
| `OPENAI_MODEL` | `gpt-4.1-mini`; structured chat output support required |
| `OPENAI_MODELS` | Allowed model list, defaults to `OPENAI_MODEL`, must include default |
| `OPENAI_TIMEOUT_SECONDS` | 30/call, >0 and <=120 |
| `OPENAI_MAX_RETRIES` | Must be 0 in every environment; no paid automatic retries |
| `WEB_CONCURRENCY` | Must be 1 in production; multiple workers/replicas unsupported |
| `MARITIME_TRUSTED_PROXY_IPS` | Launcher only; production requires actual ingress IP/CIDR allowlist |
| `MARITIME_BIND_HOST` / `PORT` | Launcher only; `127.0.0.1` / 8000 |

## AI cost and data controls

Authenticated, consented questions alone enter the inference guard. Per-owner
rate limits and the process-wide nonblocking concurrency gate apply before
provider creation. A busy workflow is rejected, not queued indefinitely. A single
worker/replica is mandatory: additional workers would multiply the in-memory
concurrency limit and login verification slots. Durable rates/budgets still rely
on the same SQLite file. No fallback provider or background inference is added.

A SQLite `BEGIN IMMEDIATE` transaction reserves the worst-case two-call token
allowance before inference: `2 * max_input + translation_output + answer_output`.
With defaults this is 42,512 tokens/question, permitting two attempts per UTC day
at the 100,000 allowance. Reservations remain charged on errors, refusals,
no-evidence results and incomplete calls. No refunds depend on missing/ambiguous
provider usage. Concurrent reservations and restart persistence are tested. Budget
storage failure/exhaustion prevents provider calls. Consent/invalid document
failures before the guard do not consume budget. All model choices remain in the
backend allowlist and both SDK calls have bounded completion output.

Prompt input is conservatively bounded using UTF-8 bytes of the system/data/schema
plus an envelope allowance; it is an application upper estimate, not a billing
reconciliation tokenizer. Too-large context is rejected rather than transmitted.
JSON bodies are bounded before parsing: login 4 KiB, import 14,100,000 bytes,
other writes 64 KiB; document/question schemas impose additional limits. Evidence
remains at most six local chunks/9,600 characters and requires explicit per-request
consent. Credentials, SQL parameters and sensitive exception messages are not
returned/logged by the application; HTTP/SDK body/header debug logs must stay off. Production suppresses SDK/HTTP/SQL debug logging and PDF parser diagnostics.

**This is a token allowance, not a guaranteed monetary spending cap.** Model prices,
provider accounting/tokenizer changes, account usage outside this app, time/clock
errors, restores of older quota state and independently running copies can differ.
Set separate OpenAI project/account limits and alerts and restrict key access.
Use a dedicated project/key, a short model allowlist and accurate UTC clock. Do
not claim live access or cost accuracy from mocked responses. No live OpenAI call
was verified in this task.

## Database, documents, backup and recovery

Migration 0003 adds sessions/rates/token ledger and a nullable original-file name.
Existing document BLOBs, chunks, FTS5 and vessel records remain compatible. New
originals are stored as owner-only UUID `.bin` files in `MARITIME_DOCUMENTS_DIR`;
their extracted text and relative filename stay in SQLite. User titles never
become paths, and no arbitrary file-serving endpoint exists. Failed imports clean
up newly created files; a crash can leave orphan files, which are not DB records.
The parser does not execute document code, but complex PDFs still need hosting
resource limits. No automatic field verification is introduced.

Both database **and** original files must survive host restarts/redeploys. The
persistence acknowledgement is operator attestation, not proof of a mounted disk.
Development emits an explicit ephemeral-storage warning when unconfirmed;
production refuses unconfirmed storage and fails if referenced originals are
missing. Monitor capacity and backup failures. SQLite/application files are not
encrypted by this app; use disk/volume encryption, restricted OS ownership and
encrypted backups. Do not commit original files, databases or environment files.

Use the operator-only backup tool with an encrypted backup destination:

```sh
python scripts/backup.py --database /var/lib/maritime/maritime.db --documents /var/lib/maritime/originals --output /backups/new-snapshot
```

It creates a new directory (never overwrites), uses SQLite's consistent backup
API, checks integrity/foreign keys, copies only referenced immutable originals
and writes `COMPLETE` last. Only snapshots with that marker are complete. Sessions
are deleted in the snapshot so restore cannot resurrect a login; quota/rate state
is preserved. Existing legacy BLOB originals remain inside the database backup.
Prefer stopping writers during release/backup; the current import-only immutable
file lifecycle also allows consistent online snapshots. A future delete/edit API
must revisit backup coordination.

Recovery: stop the backend, preserve the failed volume for diagnosis, select a
complete snapshot, check integrity, restore its database and originals together
to clean durable paths with owner-only permissions, and set both environment paths.
Reconcile today's quota against provider activity since the snapshot **before
re-enabling AI**; restoring old counters can undercount consumed allowance. Maintain
provider caps during recovery. Apply Alembic upgrades once, start one worker, log
in afresh and verify synthetic create/edit/read, documents and restart persistence.
Test recovery periodically; the test suite covers backup/restore with revoked
sessions and retained document bytes/usage state.

Downgrade 0003 refuses when file-backed originals exist, avoiding silent loss of
their metadata. Prefer restore of a pre-migration snapshot for rollback. Do not
simply downgrade the database and leave a newer executable/storage layout running.

## GitHub Pages build preparation

The app uses button/module state, not path routing; no SPA 404 rewrite is needed.
Build assets use `/Maritime-AI/` and `.nojekyll`; refresh goes through login and then
the default Dashboard. The backend URL is public configuration, never a secret.

```sh
cd frontend
npm ci
# Set this non-secret environment variable to the later backend HTTPS origin.
VITE_API_BASE_URL=https://api.example.invalid npm run build:pages
```

The sample hostname is intentionally nonfunctional. Replace it only after choosing
a backend. `build:pages` fails without an HTTPS backend origin, with credentials or
paths in that URL, or with cross-site cookie configuration. Default auth transport
is bearer; set `VITE_AUTH_TRANSPORT=bearer` explicitly if desired. Ordinary
`npm run build` still permits a same-origin `/api` reverse proxy; production
bundles contain no hardcoded localhost backend URL. Dev/preview proxies are local
configuration and are not bundled.

`.github/workflows/pages-build.yml` is a manual **build/artifact-only** workflow
with read-only repository permission; it has no Pages deployment job/permission.
It may need normal post-review integration into the default branch before GitHub
exposes manual dispatch. This task does not perform that integration. Publishing
Pages and provisioning the backend/volumes remain a separate authorized task.

## Pre-deployment checklist

- Review the single-owner/bearer decision and trust all content on the Pages origin.
- Set production secrets only in the backend host secret store; rotate leaked keys.
- Verify real durable mounts, OS permissions, volume encryption and tested backups.
- Apply migration 0003 exclusively after a complete backup.
- Use one worker/replica; configure exact ingress proxy IPs and prevent direct access.
- Ensure valid HTTPS, trusted backend Host, exact frontend CORS and ingress limits.
- Set model/token/rate limits and independent OpenAI project spend controls.
- Verify denied anonymous access, logout, expiry, forged origins, CSRF if cookie mode,
  exhausted quota and restart persistence on staging using synthetic data.
- Build Pages with the actual backend origin; verify browser CORS/mobile behavior.
- Verify real OpenAI access separately with synthetic data and explicit consent.

No infrastructure or Pages deployment, live OpenAI verification, Windows CI or
physical mobile-browser validation is claimed by this task.
