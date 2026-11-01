# Maritime AI Assistant

An offline-first vessel operations workspace for Deck Officers, Chief Officers and Masters. Task 01 provides a real SQLite-backed Ship Profile and Dashboard. Other modules are explicitly marked **Coming Soon**. The development mock provides no maritime advice.

## Requirements

- Python 3.11+ (CI: 3.12), Node.js 22.12+ (CI: 24), npm.
- Windows, Linux or macOS. CPU only; no GPU, model, API key or cloud service required.
- Internet is needed to install dependencies initially. Normal application use is local and does not require Internet. Frontend assets/fonts are bundled or system-local.

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

With the virtual environment active, run from the repository root:

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

Default database: `~/.maritime-ai/maritime.db` (Windows: the user home directory). Override with `MARITIME_DATA_DIR`, or `MARITIME_DATABASE_URL=sqlite:///absolute/path/to/file.db`. Ensure a custom database parent directory exists. Set variables before migration and startup; both commands must use the same values.

`MARITIME_ALLOWED_ORIGINS` is a comma-separated explicit origin list, defaulting to `http://127.0.0.1:5173,http://localhost:5173`. Keep it limited to trusted local frontend origins. Vite proxies relative `/api` requests to the backend, including in preview mode. Do not expose either service on a vessel LAN.

Operational records remain local. There is no telemetry, external AI call, remote font, document upload or arbitrary filesystem API. SQLite is not encrypted; OS account permissions and device disk encryption protect stored data. This single-user foundation has no login or authorization boundary against other local processes. Stop the backend before copying the database for backup. Backups and recovery UI are future work. Never commit operational databases or vessel documents.

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

Before E2E, start the backend on port 8000 using a **disposable migrated database**: set `MARITIME_DATA_DIR` to a new temporary directory in that terminal, run `alembic upgrade head`, then `uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000` from `backend`. E2E writes a synthetic profile and edits the first profile; never run it against operational data. Playwright starts Vite automatically. The smoke test covers actual API/database creation, edit, reload and mobile layout. Backend tests separately prove database persistence across application restart. CI runs backend tests, frontend unit tests and production build on Ubuntu and Windows; browser smoke is optional.

## Repository

```text
backend/       FastAPI, schemas, SQLAlchemy, Alembic migrations and Pytest
frontend/      React/TypeScript workspace, Vitest and Playwright smoke test
scripts/       Cross-platform development launcher
skills/        Future skill contract notes; no skill execution yet
docs/          Product requirements, architecture, decisions and roadmap
.github/       GitHub Actions CI
```

See [Architecture](docs/ARCHITECTURE.md), [Requirements](docs/PRODUCT_REQUIREMENTS.md), [Decisions](docs/DECISIONS.md), [Roadmap](docs/ROADMAP.md) and [Validation](docs/VALIDATION.md). This repository intentionally does not include local LLMs or an AI chat implementation.
