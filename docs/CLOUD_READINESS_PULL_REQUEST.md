# Protect private APIs and prepare Pages/cloud backend configuration

The localhost MVP exposed vessel/document APIs anonymously and had no per-owner
AI allowance. This change requires revocable owner sessions, adds login/AI rate,
concurrency and durable token-budget controls, and rejects unsafe production
configuration. Pages uses memory-only bearer auth so mobile access does not rely
on third-party cookies; same-origin cookie mode requires Secure/HttpOnly and CSRF.

Migration 0003 preserves existing records/BLOB originals and adds security state
plus configurable file-backed originals. Startup validates schema/volumes/files;
backup snapshots preserve data/quota while revoking sessions. Vite supports the
Pages base, HTTPS API origin and CSP, with an artifact-only manual build workflow.
No infrastructure is deployed and no Hybrid branch is merged.

Validation: 99 backend tests, 23 frontend tests, production/Pages builds and four
Chromium browser cases on both dev and production preview passed. Security checks
cover unauthorized access, CSRF/CORS, expiry/revocation, limits, quota races/failures,
legacy data migration and backup/recovery. Real-process proxy/restart smoke passed
with synthetic data; OpenAI SDK transport is mocked. No live OpenAI/cloud, Windows
or physical mobile verification is claimed. See docs/CLOUD_READINESS_DELIVERY.md.

Deploy only after reviewing secrets, trusted HTTPS ingress, durable storage and
provider spend caps. Single-owner/single-worker limits and token-budget accounting
trade-offs are documented. Task 02B is not started.
