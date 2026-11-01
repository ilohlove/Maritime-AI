# Engineering instructions

## Scope and standards

Use Python 3.11+, type-checked TypeScript and React function components. Keep functions focused and dependencies few. Prefer explicit schemas and meaningful names. Document units, validation rules and non-obvious tradeoffs. Do not add a framework or abstraction without a current need.

## Boundaries

FastAPI owns HTTP concerns; services own profile mutation; Pydantic schemas validate inputs; SQLAlchemy models describe storage; Alembic owns schema evolution. The frontend uses relative `/api` calls and never accesses SQLite directly. Do not place AI code in vessel persistence. AI providers implement the small Protocol; mock output must remain unmistakably non-expert. Future skills must not execute user-supplied code.

## Git and preservation

Inspect status and instructions first. Preserve existing changes. Work on `feature/<topic>` branches; Task 01 uses `feature/initial-foundation`. Never commit directly to main or merge without user approval. Cloud tasks already have isolated checkouts: use the existing checkout, do not create a worktree unless explicitly requested. Keep commits and PRs reviewable. Do not push secrets or production data.

## Required checks

Run `python -m pytest -q` from backend and `npm test`, `npm run build` from frontend before completion. Add regression tests for behavior changes, including invalid inputs and persistence. Use disposable databases. Run Playwright against an isolated backend when browser tooling is available. Report skipped or unavailable checks precisely. Do not claim Windows validation unless Windows CI has actually run.

## Security and data integrity

Bind services to loopback by default, use explicit CORS origins, reject cross-origin writes and validate all input. No telemetry, external transmission of vessel data, arbitrary file access or code execution. No real vessel information in tests. Unknown values are null, never guesses. Store measurements with decimal precision; preserve leading zeroes in identifiers. Default every new/changed field to unverified. Never auto-verify extracted data. Keep secrets, databases, dependencies and build output ignored. Review dependency advisories and retain TLS/integrity verification.

## Documentation and Done

Update README and relevant architecture/decision/requirement docs when behavior or setup changes. All required tests/build must pass; startup, database migrations, real create/edit/read and restart persistence must be verified. State known limitations, provide reproduction commands, commit the work on its feature branch, prepare a PR when supported, and wait for review before Task 02. Do not describe mock modules as complete features.
