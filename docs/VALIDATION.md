# Task 01 validation

Historical results. Current Task 02 results and explicit unverified model/Windows
gates are in [TASK_02_VALIDATION.md](TASK_02_VALIDATION.md).

Validated in Codex Cloud on Linux, Python 3.12.14, Node 24.19.0 and Chromium 154. All fixture vessel records are synthetic and stored outside Git.

| Check | Result |
| --- | --- |
| Backend `python -m pytest -q` from backend | 29 passed |
| Frontend `npm test` from frontend | 7 passed |
| Frontend `npm run build` | Passed; TypeScript and bundled production assets |
| Chromium `npm run test:e2e` using system executable | 1 passed: real create/edit/reload and mobile layout |
| Real launcher startup | Alembic migration, backend database health and Vite HTTP checks passed |
| Full service stop/restart, same SQLite file | Name, flag and exact three-decimal measurement retained via HTTP |
| Alembic upgrade repeatability, downgrade and re-upgrade | Passed in backend tests |
| npm audit | 0 known vulnerabilities after Vite/Vitest patch upgrades |
| pip-audit against pinned backend lock | No known vulnerabilities after FastAPI/Starlette/Pytest upgrades |
| Windows and Ubuntu GitHub Actions | Configuration provided; remote CI not executed in this task |

Backend checks cover unknown values, identifiers, numeric precision, cross-field constraints including merged PATCH state, failed-write atomicity, multiple independent profiles, missing IDs, provenance retention/reset, import/human-verification states, AI extraction remaining unverified, UTC timestamps, SQLite restart persistence, CORS and cross-origin write protection. One upstream TestClient deprecation warning notes a future httpx2 migration; it does not fail tests.

The cloud execution sandbox blocks event-loop/socket operations, so backend and browser checks were run with the supported execution approval path. No TLS or package integrity checks were disabled. Current advisory results are evidence at execution time, not a future security guarantee.

## Review limits

- No Windows machine was available for direct validation; Windows CI has been added but is not claimed to have passed.
- Only Dashboard and Ship Profile are implemented. AI is an explicit development mock.
- UI uses the first stored vessel; no vessel picker, verification controls, immutable audit history, backup interface, authentication or encryption yet.
- Editing state is in memory: save before changing navigation or reloading.
- No performance benchmark on physical 16 GB Windows hardware has run.
- The remote initially advertised no refs and no main branch. No main branch was created or modified. PR creation requires an existing base branch; GitHub API access also returned Forbidden in this environment.

See README for exact installation and execution commands. Task 02 is not started.
