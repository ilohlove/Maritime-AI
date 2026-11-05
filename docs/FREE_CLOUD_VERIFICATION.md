# Task 02B.1 verification and handoff

Date: 2026-11-05. Branch: feature/free-cloud-deployment-assessment.
Base commit: 7231ad0e0e6b17e3c8a7ede404b1f46a11252323.

## Findings and delivery status

- The [plan](FREE_CLOUD_DEPLOYMENT_PLAN.md) compares Render, Koyeb, HF Docker
  Spaces, Fly.io and a Codespaces developer fallback, with configuration, costs,
  architecture, storage strategy and gated step-by-step later deployment guidance.
- The [official-source ledger](FREE_CLOUD_SOURCES.md) records immutable source
  revisions and which published sites were blocked. Current HF Docker creation
  requires a paid plan; Fly has a verified no-card $1/7-day trial with five-minute
  machine stops, recommended only for a brief eligible initial test, not ongoing
  free hosting. Codespaces has limited included personal-account development quota.
- **Render/Koyeb current free/card/resource conditions remain unverified.** Old
  free YAML / free signup is not current free-hosting proof. A network-only draft
  for official documentation domains is saved but not active; Review/Save and
  Publish is the supported recovery. No access to api.openai.com was requested.
- Pages builds correctly at /Maritime-AI/, but official password-transaction and
  commercial-SaaS guidance is a rollout gate for the existing password form.
  Backend-hosted authentication handoff is proposed, not implemented or deployed.
- No managed provider is certified as recurring $0, no account eligibility was
  tested, and no cloud resource, live API call or deployment was made. A bounded
  trial recommendation does not resolve ingress/Pages policy/account eligibility.
  These unresolved requirements are explicitly blocked rather than claimed passed.

## Necessary code changes

An opt-in production-only disposable test profile requires all acknowledgement
flags, refuses persistent-storage claims and real API keys, validates an isolated
system-temp root and preserves normal production security/schema/file checks.
`start_disposable_test.py` migrates only its fresh private database. Inherited
operational paths are not opened, reset or deleted. Data and sessions intentionally
start empty on each launch. Startup and authenticated UI warn about all state loss.

Only an exact bundled fictional text payload/title/format may be imported. Arbitrary
uploads and vessel writes are denied. The UI offers that sample and disables paid
inference. Both the workflow guard and OpenAI adapter prohibit calls, including
when explicit consent is supplied. Quota loss therefore cannot authorize spending.
The dedicated API-key placeholder is a noncredential; a real key is rejected.
No mocked answer is advertised as live inference. Normal persistent behavior and
all existing security/Document AI regressions remain functional.

## Automated and process verification

| Check | Result |
| --- | --- |
| backend: `python -m pytest -q` | 117 passed; one existing Starlette/httpx deprecation warning |
| frontend: `npm test` | 25 passed |
| frontend: `npm run build` | Passed |
| frontend: `VITE_API_BASE_URL=https://api.example.invalid npm run build:pages` | Passed; placeholder hostname, not a deployed backend |
| Chromium Playwright with synthetic SDK backend + explicit disposable UI mock | 5 passed |
| Real disposable launcher, loopback proxy simulation | Passed: fresh migration, auth/TLS/Host guards, exact fixture, paid inference denial, data/session loss after restart and unrelated existing path untouched |
| Changed Python Ruff / Git whitespace | Passed |
| `python -m pip check` | No broken requirements |
| Locked Python advisory audit / npm audit including dev | No known vulnerabilities / 0 vulnerabilities |

New tests cover rejection of missing acknowledgement, development mode, missing
credentials, real API keys, false durability claims, cookie mode, wrong temporary
paths, insecure origins/hosts and retries. They confirm normal production still
rejects ephemeral storage, missing migrations/originals still prevent startup,
private routes and TLS/CORS guards remain enforced, only exact fixture storage is
allowed and providers cannot be created. Frontend tests prove the warning and
import/AI restrictions. The full baseline auth, quota, citation/PDF and bilingual
retrieval suite uses mocked inference and remains passing.

The browser suite's four baseline cases use a disposable migrated backend with
mocked official-SDK transport; the added case mocks API responses solely to verify
disposable UI controls and the 390px warning layout. It is not proof of a deployed
production cross-site connection. To reproduce all five, start the README's
synthetic backend and run from frontend:

```sh
MARITIME_E2E_SYNTHETIC=1 MARITIME_E2E_DISPOSABLE_UI=1 PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm run test:e2e
```

The UI-only case skips unless its explicit flag is set. It does not create a
cloud service or require a real API key. Physical mobile, Windows CI, live TLS,
real OpenAI access and provider deployment were not verified.

## Before any later rollout

Verify current provider terms/account free credit/card/billing controls and exact
trusted ingress topology. Resolve Pages authentication/policy guidance. Keep real
inference off for ephemeral quota storage; any paid test requires separately
authorized normal durable setup and current official unit-price verification.
Do not falsify storage_persistent, trust all forwarded peers or disable security
to satisfy a free host. Do not begin Task 02B.2 automatically.

## Changed files

- `README.md`
- `backend/app/api/documents.py`
- `backend/app/core/config.py`
- `backend/app/core/disposable.py`
- `backend/app/core/storage.py`
- `backend/app/main.py`
- `backend/app/services/ai_limits.py`
- `backend/app/services/auth.py`
- `backend/app/services/openai_provider.py`
- `backend/tests/test_disposable.py`
- `deploy/disposable-test.env.example`
- `docs/ARCHITECTURE.md`
- `docs/CLOUD_DEPLOYMENT.md`
- `docs/DECISIONS.md`
- `docs/FREE_CLOUD_DEPLOYMENT_PLAN.md`
- `docs/FREE_CLOUD_PULL_REQUEST.md`
- `docs/FREE_CLOUD_SOURCES.md`
- `docs/FREE_CLOUD_VERIFICATION.md`
- `docs/VALIDATION.md`
- `frontend/e2e/disposable-ui.spec.ts`
- `frontend/src/AuthGate.test.tsx`
- `frontend/src/AuthGate.tsx`
- `frontend/src/Documents.test.tsx`
- `frontend/src/Documents.tsx`
- `frontend/src/session.ts`
- `frontend/src/styles.css`
- `scripts/start_disposable_test.py`
