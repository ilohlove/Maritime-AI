# Online MVP V1 executed test and delivery report

Date: 2026-11-07. Linux, Python 3.12.14, Node 24.19.0, Chromium, local
PostgreSQL 17 in disposable Docker containers. Synthetic data only.

Development branch: `feature/online-mvp-v1`.
Base: `19ad79830595fd1ab13f4a0135f847e240e714f9` (`feature/signed-cloud-gateway`).
The final delivery message supplies the committed head hash. No deployment,
production setting change, merge, external account creation, private upload or
paid inference was performed. The existing deployment branch and live service
configuration were not modified. Default Wrangler configuration, existing
Render examples and both production/disposable launchers have no changes.

## Actual executed results

| Check | Result |
| --- | --- |
| Unchanged baseline backend: `python -m pytest -q` from backend | 151 passed; one Starlette/httpx deprecation warning |
| Baseline frontend tests/build | 25 passed; production build succeeded |
| Baseline gateway Node/TypeScript tests | 7 passed |
| Final backend: `python scripts/test_postgres.py -q` from root | **217 passed**, 0 skipped, 34.91 seconds; one existing TestClient/httpx deprecation warning |
| Final frontend: `npm test` | **31 passed**, 3 test files, 2.20 seconds |
| Final frontend: `npm run build` | TypeScript and Vite production build passed; JS 215.62 kB, gzip 68.09 kB |
| Final gateway: `npm test` from deploy/gateway | **8 passed**, including opt-in upload limit and unchanged default restriction |
| Playwright against isolated backend and production Vite preview | **6 passed**, 0 skipped, 11.7 seconds |
| Backend pinned dependencies: pip-audit/PyPI advisory service | No known vulnerabilities reported |
| Frontend npm lock: `npm audit --json` | 0 vulnerabilities across all severities |
| Ruff undefined/unused-symbol checks | Passed |
| `python -m pip check` | No broken requirements found |
| `git diff --check` | Passed |

The PostgreSQL helper creates its own randomly named container/password, private
test CA, certificate-verified TLS connection and isolated test schemas. It runs
`python -m pytest -q` from backend, then removes the container. PostgreSQL tests
use actual SQL, generated full-text search/GIN, transactions, role privileges,
RLS and gateway nonce storage. Object storage is mocked; this is not a Supabase
provider integration test. A persistent in-memory adapter deliberately simulates
ambiguous completed PUTs, failed deletes and restart state.

The full backend run includes the existing cross-language Worker-to-FastAPI
integration over real certificate-verified local TLS. Existing gateway signature
vectors, field tampering, duplicates, expiry, replay, proxy spoofing and
disposable restrictions are retained. The suite blocks real OpenAI HTTP transport
and uses official-SDK `httpx.MockTransport` responses for inference.

## Coverage against requested checks

| Requested area | Executed evidence |
| --- | --- |
| PostgreSQL configuration | URL normalization, TLS verify-full enforcement, pool/no-overflow settings, invalid configuration tests |
| Database migrations | Existing SQLite upgrades/data retention and empty round trips; actual PG head/round trip/GIN/RLS; offline PG SQL rendering |
| Storage abstraction | Private local permissions, no overwrite, symlink/path rejection, idempotent delete, SDK S3 stubs, sanitized failures |
| PDF upload validation/extraction | Real generated text PDF, base64/magic/size/encryption/page limits, killable parser and timeout handling |
| Ownership | Document/profile lists and all ID routes reject other owners, including questions, originals and deletion |
| Retrieval/citations | Existing multilingual queries and exact quote/ID rejection; actual PG lexical search; page/excerpt inspection; deletion index cleanup |
| Ship Profile persistence | Create/edit/restart on SQLite and PostgreSQL, exact decimal/leading-zero retention, unverified provenance |
| OpenAI mocks | Official structured SDK serialization, errors/refusal/timeouts, injection boundary, both-call token usage and validated PDF citations |
| Usage quotas | Concurrent atomic reservations, durable accounting/cost, no refunds, quota/ledger failure and default-off provider factory |
| Authentication | Existing anonymous/forged/expired/revoked sessions, rotation, logout, login limits, cookie/CSRF tests |
| Gateway | Preserved wire protocol, actual TLS integration, new PG nonce race and signed upload beyond 64 KiB |
| Disposable mode | Existing exact sample, blocked profile writes/keys/inference, isolated storage, startup/migration/security restrictions |
| Persistent startup | Missing/invalid flags/security/DB/storage configuration, no SQLite fallback, unowned data and missing ready originals |
| Failure/recovery | Interrupted PUT, indexing rollback, failed/retried delete, active-upload/delete exclusion, tampered original withheld |
| Supabase Data API risk | Migration RLS/grants; a locally created browser-like PG role granted SELECT still sees zero document rows |
| Frontend/browser | Mode/limits/default-off, consent, local search without AI, usage, real PDF import, evidence inspection, delete/reload, profile edits, Android touch |

## Fixes discovered during execution

The first changed-code regression run found the new downgrade guard also blocked
an empty migration round trip (150 passed, one failed). It was corrected to allow
only empty disposable databases while preserving the populated-data refusal.
New integration tests also exposed test client constructor/profile configuration
assumptions; the harness and explicit-credential S3 session were corrected.

A production-preview browser repeat against the same retained test database
found duplicate synthetic import filenames made a test selector ambiguous (five
passed, one failed). The test now uses a unique synthetic filename. The final
repeat against the restarted backend and production build passed all six tests.
These were executed failures and corrections, not waived checks.

## Reproduction

```sh
python -m venv .venv
# Activate .venv using the command appropriate for your shell.
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
cd backend
python -m pytest -q
cd ..
# Linux, managed local Docker socket and OpenSSL required:
python scripts/test_postgres.py -q
cd frontend
npm ci
npm test
npm run build
cd ../deploy/gateway
npm test
```

A plain backend run without `MARITIME_TEST_POSTGRES_URL` intentionally skips PG
parameter cases; that is not the final 217-pass run reported above. The helper
supplies a generated local URL/CA and does not skip them. CI now includes that
PostgreSQL helper; hosted CI/Windows has not run in this session.

Browser reproduction: set `MARITIME_DATA_DIR` to a new temporary test directory,
run Alembic head, then start
`MARITIME_E2E_SYNTHETIC=1 python -m uvicorn browser_app:create_e2e_app --factory --app-dir backend/tests --host 127.0.0.1 --port 8000`.
This development-only harness uses mocked SDK transport and real SQLite/HTTP.
From frontend, after building, run:

```sh
CI=1 MARITIME_E2E_PREVIEW=1 MARITIME_E2E_SYNTHETIC=1 \
MARITIME_E2E_DISPOSABLE_UI=1 PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium \
npm run test:e2e
```

The disposable UI browser scenario is a route-mocked UI check; actual disposable
backend security is tested separately by Pytest. Android testing is Chromium
Pixel touch emulation, not physical Android or native-app testing.

## Delivery status and deployment blockers

| Status | Components |
| --- | --- |
| Implemented and locally tested | SQLite/PostgreSQL abstraction, explicit migrations, owner scope, RLS, profile persistence, PDF parsing/limits, lifecycle recovery, both lexical engines, sources, usage/quota controls, default-off OpenAI SDK, frontend flows, signed-gateway compatibility |
| Implemented, contract/mocked tests only | S3 adapter and storage-failure workflow; real OpenAI structured integration without paid network calls |
| Implemented but not live-provider tested | Supabase pooler/S3 credentials, remote private bucket ACL, restricted backend role policies, Render startup/health lifecycle, Workers Free large-body CPU/memory |
| Planned/documented, not implemented | Automatic backup/restore orchestration, automatic legacy cloud-data transfer, OCR/malware scanning, semantic embeddings, cross-document conflict/authority engine, multi-user account management and multi-replica processing |
| Blocked by external dependencies | Provider account/plan verification and separate staging provision; valid GitHub credentials to publish the prepared PR; real inference requires explicit spending authorization |

This is **not certified production-ready**. The recommended next step is a
separately authorized synthetic staging deployment with AI disabled: verify
Supabase privacy/TLS/roles, persistent restart behavior, provider resource limits,
unsigned origin rejection, health lifecycle and a backup/restore drill. Only
then request a separately bounded real inference test and maritime answer-quality
review. See deployment and cost documents for exact required user actions and
conditional monthly estimates.

## Created and modified files

The following is the complete tracked delivery file list (generated from the
working diff before the final commit):

- `.github/workflows/ci.yml`
- `README.md`
- `backend/app/api/documents.py`
- `backend/app/api/vessels.py`
- `backend/app/core/config.py`
- `backend/app/core/gateway.py`
- `backend/app/core/object_storage.py`
- `backend/app/core/storage.py`
- `backend/app/db/session.py`
- `backend/app/main.py`
- `backend/app/models/document.py`
- `backend/app/models/security.py`
- `backend/app/models/vessel.py`
- `backend/app/services/ai_limits.py`
- `backend/app/services/auth.py`
- `backend/app/services/document_workflow.py`
- `backend/app/services/documents.py`
- `backend/app/services/openai_provider.py`
- `backend/app/services/pdf_worker.py`
- `backend/migrations/env.py`
- `backend/migrations/versions/0002_documents.py`
- `backend/migrations/versions/0004_online_mvp.py`
- `backend/pyproject.toml`
- `backend/requirements-dev.lock`
- `backend/tests/conftest.py`
- `backend/tests/test_online_mvp.py`
- `deploy/gateway/src/index.ts`
- `deploy/gateway/tests/gateway.test.mjs`
- `deploy/gateway/wrangler.online-mvp.example.jsonc`
- `deploy/online-mvp.env.example`
- `docs/ARCHITECTURE.md`
- `docs/ONLINE_MVP_V1_ARCHITECTURE.md`
- `docs/ONLINE_MVP_V1_COST_ASSESSMENT.md`
- `docs/ONLINE_MVP_V1_DEPLOYMENT.md`
- `docs/ONLINE_MVP_V1_PULL_REQUEST.md`
- `docs/ONLINE_MVP_V1_SECURITY.md`
- `docs/ONLINE_MVP_V1_TEST_REPORT.md`
- `frontend/e2e/documents.spec.ts`
- `frontend/src/Documents.test.tsx`
- `frontend/src/Documents.tsx`
- `scripts/test_postgres.py`
