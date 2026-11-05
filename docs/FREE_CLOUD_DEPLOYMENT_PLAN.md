# Task 02B.1 — zero-cost testing plan and deployment assessment

Date: 2026-11-05. Base: feature/cloud-readiness-security, 7231ad0.
Working branch: feature/free-cloud-deployment-assessment. No deployment or paid
resource creation is authorized, and Task 02B.2 is not started.

## Decision and current blockers

**No managed backend is certified as recurring $0 by this assessment.** Render is
the first candidate to verify: its official FastAPI example includes `plan: free`,
but that template dates to 2023 and current free-tier/card/storage/usage terms
could not be read through this environment's network policy. Koyeb's current
example proves FastAPI and GitHub deployment and free signup, not a free server.
Do not create either service, enter billing details or assume legacy quotas.

**Recommended verified option for a brief initial cloud test: Fly.io's eligible
no-card trial**, strictly within its $1 credit and seven-day expiry. Machines stop
after five minutes, so this suits a supervised disposable session, not a lasting
pilot or always-on free tier. If this account has no eligible trial/remaining
credit, do not add a card or choose paid compute; use the development fallback
while Render/Koyeb recurring-free terms are verified. No trial resource was created.

**Verified $0 fallback for operator development testing:** personal GitHub
Codespaces within unused included quota and with paid usage disabled/no valid
payment method. This is an on-demand test lab, not the recommended always-on
backend or a certified drop-in endpoint for Pages. Current workspace/local tests
also require no new cloud account/resource. No Codespace was created here.

A recurring-free managed-host recommendation remains **conditional on direct official Render /
Koyeb plan verification**. Review/Save and Publish the prepared documentation-only
network draft, then verify current conditions before provider selection. See the
[official source ledger](FREE_CLOUD_SOURCES.md) for immutable sources, checked dates,
limitations and all blocked published URLs. Unknown fields below are intentionally
not filled from remembered free-tier offers.

Hugging Face Docker Spaces are not a subscription-free alternative in the current
official source: Docker/Gradio creation requires PRO/Team/Enterprise even though
CPU Basic hourly compute is labelled FREE. Fly.io provides a short trial, not a
recurring free backend. The recommendation above is deliberately limited to the
user's initial testing objective; ongoing free hosting is not promised.

## Provider comparison

NV = not verified from current official documentation; unresolved, not presumed free.
Account signup/region/anti-abuse eligibility has not been tested for any provider.

| Requirement | Render | Koyeb | Hugging Face Docker Spaces | Fly.io | GitHub Codespaces fallback |
| --- | --- | --- | --- | --- | --- |
| Python/FastAPI | Yes, official example R1 | Yes, official example K1 | Yes, Docker/FastAPI H2 | Yes, official FastAPI/container guide F3; deployment not tested | Development environment; run existing Python app, not always-on hosting |
| Recurring free availability | NV; old free example is not current terms | NV; free signup is not free service | No subscription-free Docker creation per H1 | No; $1/7-day trial per F1 | Included personal-account quota, not a hosted-service plan G2 |
| Credit card | NV | NV | Paid compute/subscription payment documented H2; signup eligibility not tested | None for initial trial; continued paid use requires payment | No valid payment method: stops at quota exhaustion G2; inspect existing billing first |
| Sleep/idle | NV | NV | Free hardware sleeps when unused; exact current idle period NV H1 | Trial stops after 5 minutes F1; later lifecycle configuration-dependent | Default idle 30 minutes, session max 12 hours G2 |
| CPU/RAM | NV | NV | Default 2 CPU/16 GB H1, paid-plan creation requirement still applies | Trial up to shared-cpu-2x/4 GB F1; paid size selected | Select available machine; 2-core usage multiplier 2; RAM availability not established by read sources |
| Persistent storage | Free availability NV | Free availability NV | Default 50 GB ephemeral H1; no free durable SQLite volume established | Volumes billed $0.15/GB-month F2 | Workspace storage billed against included allowance; not a production backup/durability promise |
| Outbound HTTPS | Current free restrictions NV | Current free restrictions NV | Ports 80/443/8080 H1 | Egress metered by region F2 | Subject to account/network policy; no live OpenAI reachability test |
| GitHub deployment | Yes R1 | Yes K1 | Hub git / documented GitHub synchronization; not native GitHub web-service deployment | CI/container workflow possible; not executed | Start code workspace from repository/branch, not production deployment |
| HTTPS/env/secrets | Current runtime terms NV; verify before rollout | Current runtime terms NV; verify before rollout | HTTPS .hf.space app + runtime secrets H1/H2 | TLS 1.2/1.3 and runtime secret environment documented F3; not provisioned | Forwarding visibility/protocol caveats G3; no Pages-compatible ingress assumed |
| Monthly restrictions | NV; verify service hours, egress/build quotas and exhaustion behavior | NV; verify free instance count/regions/egress and billing | Paid subscription plus hardware/other metered features H1/H2 | No recurring free allowance established; usage-based billing F2 | Personal Free: 120 included compute units ≈60h on 2-core, 15 GB-month G2; other usage shares allowance |

## Architecture and storage

Target, after the verification/policy gates are resolved:

```text
GitHub Pages /Maritime-AI/          Backend-owned HTTPS sign-in (future reviewed handoff)
  static React + public API URL           |
  memory-only access token <--------------+
         |
  HTTPS + exact CORS + bearer
         v
Single-worker eligible Fly trial (time-limited) or later verified free provider
  production auth/TLS/Host/proxy checks
  explicit disposable synthetic test mode
  fresh temporary SQLite + temporary originals
  only bundled synthetic document, no vessel writes
  OpenAI calls forbidden
```

Production security is retained. The test-only storage exception is explicit,
requires acknowledgement and cannot claim durability. Schema revision, FTS5,
authentication, HTTPS, trusted hosts, exact CORS, model/retry settings, writable
paths and referenced-original validation still run. The existing normal production
profile still refuses ephemeral storage.

The disposable launcher creates a new private temporary directory for every run,
migrates only that new database, and overrides inherited operational storage paths.
It never resets/deletes an existing operational database. Stopping/redeploying/sleep
may lose all records and sessions; a new launch intentionally starts empty even
if old temporary files remain. Login rate/quota records are also temporary. UI and
startup logs explicitly warn after authentication and before importing documents.

Only the exact included fictional text payload/title/format is accepted. A label
claiming SYNTHETIC on arbitrary text is insufficient. File upload is disabled in
the demo UI and replaced with Import bundled synthetic document. Vessel writes
are blocked. This restriction is stronger than trusting users to avoid real data.
The normal persistent profile and Document AI pipeline remain unchanged.

**Paid inference is forbidden in disposable mode.** A lost SQLite ledger could
otherwise reset spending and login counters. The mode accepts only the known
noncredential `DISABLED-DISPOSABLE-TEST` placeholder instead of a real OpenAI key;
both the inference guard and SDK adapter reject calls before provider construction.
Explicit consent cannot override this. No synthetic answer is presented as a real
model answer. This phase tests auth/storage/UI only, not live document answering.

## GitHub Pages readiness and policy gate

Technical checks: Vite base `/Maritime-AI/`, public `VITE_API_BASE_URL` restricted
to an HTTPS origin, CSP with explicit connect-src, .nojekyll, state/button routing,
no token/localStorage persistence and memory-only bearer sessions. Existing mobile
Chromium emulation passed in Task 02A; new warning/import UI has unit coverage.
No physical Android/iOS cross-site or deployed CORS check has been performed.

Pages is available on GitHub Free for public repositories; private-repo eligibility
may require a paid plan. Verify this repository/account rather than assuming it.
Official Pages guidance says sites should not send passwords or credit-card data;
it also restricts hosting primarily commercial SaaS. **The current Pages-hosted
password form is therefore not cleared for public rollout by this assessment.**
Do not interpret successful builds/CSP/bearer auth as resolution of that guidance.

Before any later deployment, review a backend-hosted sign-in page and a short-lived,
one-time, origin-bound/PKCE-style token handoff to the static frontend, without
putting reusable tokens/passwords in URLs. This is a proposed prerequisite, not
implemented here and not authorization to start Task 02B.2. Alternatively review
a different frontend host's current terms. Until resolved, keep credential entry
on a trusted local/backend interface; no public Pages password collection.

## Required test-only configuration

Use [deploy/disposable-test.env.example](../deploy/disposable-test.env.example).
This file is a reference, not an automatically loaded environment or a resource
manifest. Set non-secret values through the chosen platform's settings only after
all gates are cleared. Set a unique owner password hash as a backend secret.
Never reuse an operational account password in a disposable test lab.

- `MARITIME_ENV=production`, `MARITIME_AUTH_TRANSPORT=bearer`, one worker.
- `MARITIME_DISPOSABLE_TEST_MODE=true`.
- `MARITIME_DISPOSABLE_ACK=SYNTHETIC_ONLY_DATA_LOSS_NO_PAID_AI`.
- `MARITIME_STORAGE_PERSISTENT=false` (never lie with true on ephemeral storage).
- `OPENAI_API_KEY=DISABLED-DISPOSABLE-TEST` (not a secret/live key; real keys rejected).
- Real `MARITIME_PASSWORD_HASH`, exact backend domain/Pages origin, verified ingress
  proxy IP/CIDR allowlist and secured platform bind host/PORT.
- Do not set a production database/original path for this launcher; it creates and
  validates `MARITIME_DISPOSABLE_ROOT`, SQLite and originals inside a new temp root.

Model allowlist, zero retries and conservative input/output/rate limits remain
validated. They do not enable inference in this profile. Do not use the old
`browser_app` synthetic SDK test factory for cloud hosting.

## Later deployment runbook — gated, not executed

1. Select only an eligible no-card Fly trial with positive unused credit, or stop
   and complete direct Render/Koyeb documentation verification through the supported
   network review. Record current prices/card checks, resource/usage quotas,
   exhaustion behavior, outbound 443 and ephemeral storage semantics. Proceed only
   if the chosen account/region explicitly offers $0 without automatic paid upgrade.
   For Fly, confirm the verified trial limits rather than calling its plan recurring
   free. If eligibility/credit is absent, stop; do not enter billing details or choose
   paid compute. Never open extra accounts to evade trial limits.
2. Resolve Pages password/commercial-use guidance and review the backend-hosted
   authentication handoff. Re-test auth/CORS/mobile behavior before public use.
3. Confirm the host's actual trusted TLS ingress peers and header sanitization.
   The launcher rejects `*` and all-address trust; never guess IPs or remove the
   HTTPS guard. If the provider cannot supply a compatible verified ingress model,
   stop and review its trust architecture before deployment.
4. After separate deployment authorization, for Fly first prepare/review a
   container from this GitHub checkout: Python 3.12, repository-root build context,
   install the pinned backend lock and editable backend, include backend/ and
   scripts/, and execute `python scripts/start_disposable_test.py`. Exclude .git,
   .env, databases, originals, dependencies and backups from the build context.
   No container recipe was built/deployed in this assessment. The official F3
   FastAPI guide and GitHub Actions guide describe Fly's deployment approach.
   `fly launch --no-deploy` would create configuration/app metadata and is NOT run
   here. At the later authorized deployment use one Machine (`fly deploy --ha=false`),
   no volume, no Postgres/add-ons/static egress/dedicated IPv4, and a reviewed memory
   size within trial limits/credit. Run the container as a non-root user, keep only
   runtime files, and use /tmp for its isolated test state. The default two-Machine deployment is unsuitable
   for this single-worker SQLite app. Verify every proposed line item before create.
   Native-build providers instead connect GitHub to the approved host,
   choose the reviewed branch/commit and a verified free instance. Root directory
   must include both backend/ and scripts/. Use Python 3.12 if currently supported.
   Build from root: `python -m pip install -r backend/requirements-dev.lock` then
   `python -m pip install --no-deps -e backend`.
5. Configure the explicit test-only variables and owner secret. Set the actual
   backend DNS name and provider PORT. For a container/web-service host that needs
   it, bind 0.0.0.0 only behind its verified ingress. Start command from root:
   `python scripts/start_disposable_test.py` (also the Fly container entrypoint). Do not run migrations against an
   operational path; this command validates flags and migrates its fresh temp DB.
6. Verify HTTPS health, denied anonymous access, logout/expiry, exact origins,
   fake Host rejection, visible data-loss warning, exact synthetic import and
   `disposable_ai_disabled` for consented inference attempts. Restart and confirm
   data loss/session invalidation is explicit and OpenAI remains disabled.
7. Build frontend with `VITE_API_BASE_URL=https://<verified-backend-domain>` and
   `VITE_AUTH_TRANSPORT=bearer`, using `npm run build:pages`. Do not put owner
   passwords, password hashes or OpenAI credentials in Vite/GitHub Pages settings.
8. Only after the policy/auth gate and a new deployment authorization, configure
   Pages Source=GitHub Actions and an appropriately reviewed publishing workflow
   targeting `https://ilohlove.github.io/Maritime-AI/`. The current workflow is
   **build/artifact-only** and does not publish. Do not merge the default/Hybrid
   branch simply to enable this task. Check assets/CSP/API origin, then physical
   mobile browsers. No deploy job/resource was created or triggered here.
9. Monitor the verified free quota, cold starts and suspended-service behavior.
   Stop at exhaustion rather than upgrading. Do not use keepalive traffic to
   evade free-tier sleep restrictions. Delete the disposable service/temporary
   data after testing; do not treat a free service as an operational archive.

For the verified Codespaces development fallback: confirm personal-account unused
quota/billing controls first; do not create an organization-billed or paid workspace.
Select a small machine, stop promptly and account for storage until deletion.
Use private test forwarding and synthetic data, not a permanent public API for
Pages. No Codespace was created or forwarding published in this task.

## Preparing a separately authorized real OpenAI test

Keep the current no-live-call rule. A future real test uses the normal production
profile with genuine durable budget storage (or the existing local durable setup),
not disposable mode with `storage_persistent=true`. Configure a dedicated backend
key, a single approved structured-output model, `OPENAI_MAX_RETRIES=0`, concurrency
1, low rate, input cap 20000, translation output 128, answer output 256 and daily
allowance 45000. The worst-case reservation is 40384 tokens, allowing one attempt
per UTC day under those settings. Some questions may fail tight output caps; do
not silently increase limits/retry. Use only the synthetic document and fresh
explicit consent, after separate authorization for the paid call.

Current OpenAI unit prices/minimum funding could not be directly verified. Read
https://openai.com/api/pricing/ before authorizing; model price is not inferred
from a ChatGPT subscription. Application token limits are not a monetary guarantee
and provider budget alerts may not be hard spending stops. Confirm actual provider
controls. No API key or paid call is needed for the disposable hosting test.

## Cost estimate

| Item | Estimate / boundary |
| --- | --- |
| Assessment, local automated tests | No new provider resource or API charges created by this task |
| Pages static test assets | $0 only with an eligible free/public repository and within quotas; policy/auth gate still applies |
| Eligible Fly trial | $0 out-of-pocket only within the verified $1/7-day no-card trial; five-minute machine stops and service loss on exhaustion are accepted |
| Render/Koyeb managed backend | **Not certified $0** until direct current terms and account eligibility are verified |
| Codespaces developer fallback | $0 within unused personal quota and blocked paid usage; storage also consumes the allowance |
| Temporary SQLite/originals | No separate volume purchase in test-only mode; all data expendable, no durable service promised |
| OpenAI during disposable phase | $0 API usage: real keys/calls forbidden, not merely budgeted |
| Authorized real OpenAI phase | Usage-billed unless actual account credits cover it; exact current rates/top-up unknown, no fixed dollar amount invented |
| Optional paid fallback (not recommended for this request) | Fly source example 512 MB machine + 1 GB volume ≈$3.84/30 days before egress/tax; memory may be inadequate for complex PDFs |

For a future model priced `P_in`/`P_out` per million tokens, the conservative
40384-token workflow estimate above is at most `(40000*P_in + 384*P_out)/1000000`
under the application's token estimate. This is not an invoice guarantee or proof
of current prices. Hosting being free does not make OpenAI inference free.

## Remaining verification and delivery status

Provider-site reads remain blocked until the environment documentation allowlist
is reviewed/published. Render/Koyeb current free terms, account/card eligibility,
actual provider proxy topology, Pages authentication guidance resolution and
physical mobile testing remain gates. These prevent an unconditional ongoing managed
$0 deployment recommendation. The Fly trial is a bounded initial-test option only;
none of these gates is silently marked passed.

Code changes and tests are summarized in [verification report](FREE_CLOUD_VERIFICATION.md).
No hosting account/resource, public forwarding, Pages site, live API call or paid
resource was created. No Hybrid branch was merged and Task 02B.2 is unstarted.
