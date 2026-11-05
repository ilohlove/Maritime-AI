# Maritime AI Assistant

A local vessel workspace and API-first maritime document assistant. Dashboard and Ship Profile work offline. Documents and AI Assistant support local PDF/text import and consent-gated OpenAI question answering with validated source quotes. Equipment, Checklists and Settings remain planned. The legacy development mock is preserved and provides no maritime advice.

## Requirements

- Python 3.11+ (CI: 3.12), Node.js 22.12+ (CI: 24), npm.
- Windows, Linux or macOS. CPU only; no GPU, model, API key or cloud service required.
- Internet is needed for dependency installation and online document questions. Vessel profiles and document import stay local and work without an API key. Frontend assets/fonts are bundled or system-local.

## Cloud readiness and authentication

Task 02A adds mandatory authentication for private APIs and prepares GitHub Pages
plus an HTTPS backend. **Nothing has been deployed.** See
[cloud setup, security decisions, environment reference and backup/recovery](docs/CLOUD_DEPLOYMENT.md).
The cloud runtime is one owner, one worker/replica and mounted persistent storage.
GitHub Pages uses memory-only bearer sessions, avoiding third-party mobile cookies.
All private UI/data requires sign-in; reloading the page requires sign-in again.

## Free-hosting assessment (Task 02B.1)

See [free testing plan and provider comparison](docs/FREE_CLOUD_DEPLOYMENT_PLAN.md)
and its [official-source ledger](docs/FREE_CLOUD_SOURCES.md). Current Render/Koyeb
free-tier terms could not yet be directly verified under this environment's
network policy; no managed provider is certified as recurring $0. The verified Fly no-card trial
is recommended only for brief eligible initial testing, with $1/7-day credit and
five-minute machine stops; no trial was started. A free signup,
old free template, temporary credit or free hardware inside a paid subscription
is not enough. No deployment has occurred.

An explicit production-secured disposable profile now exists for synthetic-only
storage/UI tests: `scripts/start_disposable_test.py`. It accepts only the exact
bundled document, blocks vessel writes and all real AI, shows a data-loss warning,
and validates a fresh isolated temporary SQLite/originals directory. It does not
weaken the normal persistent production profile. Do not put real API keys or
operational records into it. See the plan before using its inert environment sample.

The assessment also flags official Pages guidance about password transactions and
commercial SaaS. The existing password form is not cleared for public Pages
rollout solely because the static build passes. Resolve that gate before any later
publication; backend-hosted authentication is proposed, not implemented in this task.

## Install

From the repository root:

```sh
python -m venv .venv
```

Activate on Windows PowerShell: `.venv\Scripts\Activate.ps1`; on Linux/macOS: `source .venv/bin/activate`. If PowerShell activation is restricted, call `.venv\Scripts\python.exe` directly instead.

```sh
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
npm --prefix frontend ci
```

## Run locally

With the virtual environment active, first generate a private owner password
hash and configure `MARITIME_PASSWORD_HASH` in the backend environment. For example,
on Linux/macOS (the password is read interactively, not placed in shell history):

```sh
export MARITIME_PASSWORD_HASH="$(python scripts/hash_password.py)"
```

On PowerShell, capture the generator output in `$env:MARITIME_PASSWORD_HASH`.
The app does not auto-load `.env`; never commit passwords or hashes. Set optional
`MARITIME_ADMIN_USERNAME` (default `admin`). Without a hash, development APIs stay
locked. Then run from the repository root:

```sh
python scripts/dev.py
```

This applies Alembic migrations and starts FastAPI on **127.0.0.1:8000** and Vite on **127.0.0.1:5173**. Open the latter address in your local browser. Ctrl+C stops both. The backend must pass its database health check before the frontend starts. Equivalent commands in separate terminals:

```sh
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

```sh
cd frontend
npm run dev
```

Create a profile, save, return to Dashboard, edit the profile, then restart the application to confirm persistence. Blank fields mean unknown. Decimal measurements use metres, tonnes and kilowatts, with up to three decimal places. GT and NT are dimensionless tonnage indices, not weights. IMO checksum and nine-digit MMSI format are validated; identifier validation does not confirm a real registration.

For a local production bundle, run `npm run build` then `npm run preview` from `frontend`, with the backend running separately. Preview uses port 5173 to match the default trusted origins; stop Vite dev first.

## Local data and configuration

### Synthetic UI preview and Android review

After installing dependencies, use the active backend virtual environment:

```sh
python scripts/synthetic_preview.py
```

This starts the existing React UI on `http://127.0.0.1:5173` and FastAPI on
`127.0.0.1:8000`, applies migrations, and seeds **SYNTHETIC PREVIEW VESSEL — TEST DATA**.
It overrides inherited database settings with the ignored
`.preview-synthetic/maritime.db`; it never opens the normal operational database.
Seeding only occurs when this preview database is empty, so saved edits survive
page reloads and server restarts. All seeded fields are unverified; IMO/MMSI are
left blank to avoid associating the profile with a real vessel. Use synthetic data only.

This Codex session has no available preview/port-forwarding capability, so its
loopback URLs cannot be opened from an Android phone. No public deployment or
tunnel is created. See [preview validation and alternatives](docs/PREVIEW.md).

For interactive phone review, run this checkout on a computer on the same trusted
Wi-Fi as the phone. Find that computer's local IPv4 address and substitute it below:

```sh
python scripts/synthetic_preview.py --host 0.0.0.0 --origin http://192.168.1.20:5173
```

Open `http://192.168.1.20:5173` in Android Chrome. Only the synthetic preview frontend
is bound to the network; the backend stays on loopback and Vite proxies `/api`.
The origin is explicitly trusted for saving and its hostname is allowed in Vite.
Allow port 5173 on the computer's private-network firewall if necessary. Do not
forward the port on a router. Ctrl+C stops both servers. This exception to the
normal loopback-only setup is for this synthetic phone review only.

If an authenticated Codex port preview becomes available in another session, use
its exact HTTPS origin with `--origin` and `--host 0.0.0.0`, and forward frontend
port 5173 only. The script does not create or publish that forwarding itself.

Default database: `~/.maritime-ai/maritime.db` (Windows: the user home directory). Override with `MARITIME_DATA_DIR`, or `MARITIME_DATABASE_URL=sqlite:///absolute/path/to/file.db`. Ensure a custom database parent directory exists. Set variables before migration and startup; both commands must use the same values.

`MARITIME_ALLOWED_ORIGINS` is a comma-separated explicit origin list, defaulting to `http://127.0.0.1:5173,http://localhost:5173`. Keep it limited to trusted local frontend origins. Vite proxies relative `/api` requests to the backend, including in preview mode. Do not expose either service on a vessel LAN.

Operational records and imported original documents remain local by default. There is no telemetry, remote font or arbitrary filesystem API. Only an explicitly authorized document question sends the question and bounded retrieved text to OpenAI; vessel profile data is never included automatically. SQLite is not encrypted; OS account permissions and device disk encryption protect stored data. Private APIs now require owner authentication even on localhost. This remains a single-owner application, not OS-process isolation or a multi-tenant service. Back up SQLite and original files together with `scripts/backup.py`; see the cloud operations guide. Recovery UI remains future work. Never commit operational databases or vessel documents.

## Online document questions

Install the updated backend lock file, then apply `alembic upgrade head` from
`backend` before starting the backend. Migration 0002 adds the library/FTS5; migration 0003 adds durable authentication,
rate/budget state and file-backed originals without changing vessel records. The default SQLite build must support
FTS5. Keep a local backup before upgrading an operational database.

Set the following variables **only in the backend process environment**. The app
does not auto-load `.env` files; do not put keys in frontend/Vite variables.

| Variable | Default / requirement |
| --- | --- |
| `OPENAI_API_KEY` | Required only for online questions; backend secret, never committed |
| `OPENAI_MODEL` | `gpt-4.1-mini`; choose a model supporting structured chat outputs |
| `OPENAI_MODELS` | Comma-separated allowed models; defaults to `OPENAI_MODEL`, must contain it |
| `OPENAI_TIMEOUT_SECONDS` | `30`, greater than 0 and at most 120, per SDK request |
| `OPENAI_MAX_RETRIES` | `0` required; automatic paid retries are disabled, no fallback |

The existing `MARITIME_DATA_DIR`, `MARITIME_DATABASE_URL` and
`MARITIME_ALLOWED_ORIGINS` variables retain their meanings. A key is not needed to
start the application, migrate, use profiles or import documents. Restart the
backend after configuration changes. `GET /api/ai/providers` reports configuration,
not verified connectivity; it requires login and never returns credentials. The
public health endpoint now returns only `{"status":"ok"}`.

Open **Documents** or **AI Assistant**, import a PDF or `.txt`, select it, choose
an allowed model and type a question in Vietnamese or English. Authorize that
individual request using the checkbox, then ask. Changing the question, document,
model or provider clears consent, as does every submitted attempt. Import alone
never calls OpenAI. Both pages expose the same document workflow.

Each authorized request first sends the question alone for English/Vietnamese
search translation. SQLite FTS5 then retrieves at most six chunks, totaling at
most 9,600 characters, from that document. Only those chunks and the question
are sent for answer generation. The original file is never uploaded through an
OpenAI file API; a short document's entire text may fit inside the retrieved
excerpts, as disclosed in the consent text. Answers render exact validated quotes
and page numbers taken from the local index. PDF page numbers are physical pages,
not printed page labels; text pages are separated by form-feed characters.

Limits: original file 10 MB, PDF at most 300 pages, extracted text at most 1 million
characters. Encrypted, malformed and scanned PDFs without readable text are
rejected. Import accepts JSON (`format: text` with UTF-8 text or `format: pdf` with
base64 bytes). New originals live in `MARITIME_DOCUMENTS_DIR` (default: a
`documents` sibling of the database); chunks and legacy originals remain in SQLite.
Treat both locations and backups as sensitive. No question history is persisted.

Retrieval errors, provider errors, model refusal and citation failure have
separate actionable codes; an empty search result never claims the document lacks
the answer. Generation uses no tools, cannot execute document instructions or
mutate vessel records, and treats source text as untrusted. Exact quote checks do
not establish that a paraphrase is correct. Review sources before operational use.
Do not enable SDK/HTTP debug body logging on sensitive data. `store=False` is sent
to OpenAI; this does not override the provider's account-level data retention policy.

No live OpenAI call was verified during this task: this environment has no valid
key and its network allowlist excludes `api.openai.com`. For a live check, configure
a backend key and allow HTTPS to that host in the environment's supported network
configuration, then ask against a synthetic document with explicit consent.
See [assessment](docs/ONLINE_API_ASSESSMENT.md) and
[implementation and validation report](docs/ONLINE_API_IMPLEMENTATION.md).

## Testing

With the virtual environment active, run from `backend` (also used in CI):

```sh
cd backend
python -m pytest -q
```

From `frontend`:

```sh
npm test
npm run build
```

Optional real-browser smoke test (requires Chromium download once):

```sh
npx playwright install chromium
npm run test:e2e
```

Configure `MARITIME_PASSWORD_HASH` for the isolated backend and `MARITIME_E2E_PASSWORD` for Playwright. The document Q&A browser case requires the synthetic SDK harness described below; it is explicitly skipped against a normal backend. Before the existing profile E2E cases, start the backend on port 8000 using a **disposable migrated database**: set `MARITIME_DATA_DIR` to a new temporary directory in that terminal, run `alembic upgrade head`, then `uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000` from `backend`. E2E writes a synthetic profile and edits the first profile; never run it against operational data. Playwright starts Vite automatically. The smoke test covers actual API/database creation, edit, reload and mobile layout. Backend tests separately prove database persistence across application restart. CI runs backend tests, frontend unit tests and production build on Ubuntu and Windows; browser smoke is optional.

To run **all four browser cases** without paid API calls, use a new empty
local directory as `MARITIME_DATA_DIR` and start the test-only backend from
`backend` (with the virtual environment active):

```sh
# Set MARITIME_DATA_DIR to a disposable directory, and MARITIME_E2E_SYNTHETIC=1.
python -m alembic upgrade head
python -m uvicorn browser_app:create_e2e_app --factory --app-dir tests --host 127.0.0.1 --port 8000
```

Then from `frontend`, with `MARITIME_E2E_SYNTHETIC=1` also set in that terminal:

```sh
npm run test:e2e
```

The harness sets an unmistakably synthetic test-only password (`synthetic-browser-password`), used automatically by Playwright only with its synthetic flag. It is never a production default. The harness uses real HTTP, SQLite, FTS5, extraction and citation validation with
the official SDK backed by an in-memory mock transport. Responses are marked
**SYNTHETIC SDK RESPONSE**. Never deploy that test factory. Optionally set
`PLAYWRIGHT_CHROMIUM_EXECUTABLE` to an installed Chromium executable instead of
downloading Playwright's browser. Mobile checks use Chromium device emulation;
they do not establish physical Android validation.

For GitHub Pages, set the non-secret `VITE_API_BASE_URL` to the later HTTPS backend
origin and run `npm run build:pages` from `frontend`. Assets use `/Maritime-AI/`.
The included manual workflow only builds an artifact and has no deployment step.
See the [cloud guide](docs/CLOUD_DEPLOYMENT.md) before configuring public hosting.

## Repository

```text
backend/       FastAPI, schemas, SQLAlchemy, Alembic migrations and Pytest
frontend/      React/TypeScript workspace, Vitest and Playwright smoke test
scripts/       Cross-platform development launcher
skills/        Future skill contract notes; no skill execution yet
docs/          Product requirements, architecture, decisions and roadmap
.github/       GitHub Actions CI
```

See [Architecture](docs/ARCHITECTURE.md), [Requirements](docs/PRODUCT_REQUIREMENTS.md), [Decisions](docs/DECISIONS.md), [Roadmap](docs/ROADMAP.md) and [Validation](docs/VALIDATION.md). This checkout has no Qwen3/llama.cpp runtime. The document provider Protocol allows future local adapters without changing extraction, retrieval or citation validation.
