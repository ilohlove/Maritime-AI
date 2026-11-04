# Task 02A pre-implementation assessment

Base: feature/online-api-mvp, commit 38f1472. No deployment is authorized.

- React uses in-memory module navigation, so no history-router fallback is needed.
  Vite lacks the GitHub Pages /Maritime-AI/ base; API URLs assume the dev proxy.
- FastAPI starts without local models. Dependencies are pinned. Alembic 0001/0002
  owns SQLite schema and FTS5; startup health only checks vessels.
- PDF/text import is JSON/base64, bounded, local and untrusted. Original bytes
  and chunks currently live in SQLite. No filesystem document serving exists.
- OpenAI uses a backend environment key, model allowlist, structured outputs,
  bounded evidence and sanitized failures, but optional retries and fixed output
  limits exist; there are no user rate/concurrency/budget controls.
- All data endpoints are currently anonymous. Origin checking, JSON-only writes
  and explicit localhost CORS are useful browser controls, not authentication.
  No sessions, logout, login throttling, trusted-host or production HTTPS guard.
- No persistent-volume declaration, cloud startup validation, backup/recovery
  procedure or GitHub Pages build configuration is supplied yet.

Implementation decisions: single private owner with a scrypt password hash,
opaque random expiring/revocable sessions stored as digests in SQLite. Default
bearer transport stores tokens only in browser memory (reload requires login),
so Pages/mobile do not depend on third-party cookies. Optional same-origin cookie
transport requires Secure/HttpOnly/SameSite=Strict and synchronizer CSRF tokens.
No public signup, multi-tenant isolation or enterprise identity is claimed.

Add durable login/AI rate counters and a conservative atomic daily token budget;
reserve worst-case tokens before inference, never refund ambiguous failures.
Use one backend worker/replica with bounded AI concurrency. Add production
configuration and migration/storage validation, configurable original-file storage
with legacy SQLite blobs retained, and manual deployment preparation only.
