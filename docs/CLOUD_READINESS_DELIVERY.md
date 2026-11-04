# Task 02A delivery — cloud readiness and security

Date: 2026-11-05. Branch: `feature/cloud-readiness-security`.
Base: `feature/online-api-mvp` / `38f1472b371f71531b46d9baa2e6e96b5c9307d1`.

## Assessment and final implementation

[Assessment](CLOUD_READINESS_ASSESSMENT.md) records the pre-change frontend,
backend, migrations, document storage, OpenAI configuration and missing security
boundaries. The existing application was extended, not rebuilt; no Hybrid branch
was merged and Task 02B remains unstarted.

- All private routes now require an expiring/revocable opaque owner session.
  Scrypt password hashes live in backend secret configuration; token digests,
  credential versions and expiry live in SQLite. Explicit logout and rotation
  revoke access. Login has durable IP/global rate limits and one hash-verification
  slot. Public surfaces are minimal health, login and CORS preflight.
- Pages uses bearer tokens in browser memory only, with login/expiry/logout UI.
  Optional same-origin cookies are HttpOnly/Secure/SameSite=Strict and require a
  synchronizer CSRF token plus allowed Origin on writes. Cross-site Pages cookie
  configuration is rejected instead of relying on third-party mobile cookies.
- AI requests require authentication and consent, model allowlisting, body/input/
  output caps, owner rate limits, nonblocking concurrency and atomic pre-reserved
  daily token allowance. Missing/failed quota storage fails closed. No automatic
  SDK retry or provider fallback; failures never refund uncertain usage.
- Production validates required secrets, HTTPS frontend origins, trusted backend
  hosts, persistent storage acknowledgement and one-worker operation. The launcher
  trusts only explicit ingress IP/CIDRs. API HTTPS/no-store/security headers and
  sanitized validation/unexpected errors reduce accidental data disclosure.
- Migration 0003 preserves existing vessel/document records and BLOB originals,
  adds security state and references for new UUID original files. Both paths are
  configurable. Startup checks migrations, FTS5, writable volumes and referenced
  files. The consistent backup tool clears sessions only in snapshots and retains
  quotas/originals; restore and downgrade safeguards are tested.
- Vite builds under `/Maritime-AI/`, supports a public HTTPS backend URL and adds
  CSP/.nojekyll. Preview uses the same base. Dev/preview proxies rewrite Host to
  the loopback backend while preserving explicit browser Origin checks. Private
  UI wording reflects backend storage, including cloud configurations.
- The manual Pages workflow builds/uploads an artifact only. No deployment job,
  infrastructure provisioning, database service migration or paid resource exists.

## Test results

| Check | Result |
| --- | --- |
| `cd backend && python -m pytest -q` | 99 passed; one pre-existing Starlette/httpx TestClient deprecation warning |
| `cd frontend && npm test` | 23 passed |
| `cd frontend && npm run build` | Passed (TypeScript + production bundle) |
| `VITE_API_BASE_URL=https://api.example.invalid npm run build:pages` | Passed; hostname is a nonfunctional configuration placeholder |
| Chromium Playwright, synthetic backend, dev | 4 passed |
| Chromium Playwright, synthetic backend, production preview at Pages base | 4 passed |
| Negative Pages configuration builds | Correctly reject missing backend, HTTP backend, credential URL and cross-site cookie mode |
| Build artifact inspection | Correct base/CSP/.nojekyll; no localhost backend URL or synthetic test credentials bundled |
| Changed Python Ruff / Git whitespace | Passed |
| Python dependency audit / npm audit (including dev) | No known vulnerabilities found / 0 vulnerabilities |
| `python -m pip check` | No broken requirements |

Security coverage includes anonymous endpoints, login failure/rate persistence,
forged/revoked/expired sessions, password rotation, cookie flags and CSRF, exact
CORS/credentials, trusted hosts/proxy spoofing, production missing-secret/HTTP
rejection, streamed body bounds, redacted errors, AI input/output limits, atomic
concurrent quota reservation, budget exhaustion/storage failure before provider
calls, concurrency/rate rejection and no refunds after provider failure.

Existing Document AI regressions still cover PDF extraction, bilingual retrieval
with mocked translation, source validation, missing evidence, provider errors,
consent and legacy mock preservation. Additional tests cover legacy originals
across migration, configurable original storage, missing-volume startup failure,
backup/restore with revoked sessions and retained quota, and guarded downgrades.

The real production launcher was also exercised on loopback with synthetic secrets
and **simulated** trusted/untrusted proxy headers. Real processes verified denial
of anonymous requests, create/edit/read, file/session persistence after restart,
logout revocation and rejection of all-address proxy trust. This is not a public
HTTPS/TLS or live cloud integration test. OpenAI calls in automated tests use mock
transport; no live OpenAI verification is claimed.

Browser checks use a disposable migrated database and the test-only
`browser_app:create_e2e_app` with clearly synthetic SDK output. That factory refuses production mode. To reproduce, use
the README harness commands with `MARITIME_E2E_SYNTHETIC=1`. Add
`MARITIME_E2E_PREVIEW=1` after `npm run build` for the production preview variant;
`PLAYWRIGHT_CHROMIUM_EXECUTABLE` can select an installed Chromium. Screenshots of
login and document sources were reviewed at 390px. Mobile checks are emulation,
not physical Android/iOS. Windows CI has not been verified in this session.

## Security decisions, limits and deployment prerequisites

The [cloud operations guide](CLOUD_DEPLOYMENT.md) provides all environment variables,
startup/migration/Pages build commands, storage and backup/recovery instructions,
security checklist and the cross-site auth trade-offs. Deploy only after selecting
a real HTTPS backend/ingress, configuring secrets and exact proxy/host/CORS lists,
mounting and verifying durable storage, and testing restore with provider caps.

Known limits: one owner and one worker/replica, no MFA/recovery UI/tenant ownership,
memory-only re-login after refresh, shared GitHub Pages origin trust and meta-CSP
limitations, no PDF resource sandbox/OCR, no application disk encryption, operator
attestation of actual durability, and an intentionally conservative token allowance
rather than guaranteed monetary billing control. Restored quota state, multiple
independent instances/keys and provider accounting need external spend limits and
operator reconciliation. There is no live provider, public HTTPS, physical mobile
or Windows validation. No deployment occurred.

GitHub CLI still reports its configured token invalid; Git transport is checked
separately for push and remote SHA verification. A review-ready PR description is
provided in [CLOUD_READINESS_PULL_REQUEST.md](CLOUD_READINESS_PULL_REQUEST.md).
Actual synchronization status and commit SHA are reported after committing/pushing,
not inferred from local success or a PR creation link.

## Changed files

- `.github/workflows/pages-build.yml`
- `.gitignore`
- `README.md`
- `backend/app/api/auth.py`
- `backend/app/api/documents.py`
- `backend/app/core/config.py`
- `backend/app/core/storage.py`
- `backend/app/main.py`
- `backend/app/models/document.py`
- `backend/app/models/security.py`
- `backend/app/services/ai_limits.py`
- `backend/app/services/auth.py`
- `backend/app/services/document_workflow.py`
- `backend/app/services/documents.py`
- `backend/app/services/openai_provider.py`
- `backend/migrations/env.py`
- `backend/migrations/versions/0003_security.py`
- `backend/tests/browser_app.py`
- `backend/tests/conftest.py`
- `backend/tests/test_documents.py`
- `backend/tests/test_security.py`
- `backend/tests/test_vessels.py`
- `deploy/backend.env.example`
- `docs/ARCHITECTURE.md`
- `docs/CLOUD_DEPLOYMENT.md`
- `docs/CLOUD_READINESS_ASSESSMENT.md`
- `docs/CLOUD_READINESS_DELIVERY.md`
- `docs/CLOUD_READINESS_PULL_REQUEST.md`
- `docs/DECISIONS.md`
- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/ROADMAP.md`
- `docs/VALIDATION.md`
- `frontend/e2e/auth.spec.ts`
- `frontend/e2e/documents.spec.ts`
- `frontend/e2e/fixtures.ts`
- `frontend/e2e/preview-mobile.spec.ts`
- `frontend/e2e/workspace.spec.ts`
- `frontend/package.json`
- `frontend/playwright.config.ts`
- `frontend/public/.nojekyll`
- `frontend/src/App.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/AuthGate.test.tsx`
- `frontend/src/AuthGate.tsx`
- `frontend/src/Documents.test.tsx`
- `frontend/src/Documents.tsx`
- `frontend/src/ShipProfile.tsx`
- `frontend/src/api.ts`
- `frontend/src/main.tsx`
- `frontend/src/session.ts`
- `frontend/src/styles.css`
- `frontend/src/test-setup.ts`
- `frontend/vite.config.ts`
- `scripts/backup.py`
- `scripts/hash_password.py`
- `scripts/start_backend.py`
