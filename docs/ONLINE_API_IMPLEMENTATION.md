# Online API Task 01 implementation and validation

Date: 2026-11-05. Branch: `feature/online-api-mvp`.

## Assessment and implementation

See [the pre-implementation assessment](ONLINE_API_ASSESSMENT.md). This checkout
contained vessel profiles and an honest mock, but none of the assumed document,
FTS5, hybrid retrieval or Qwen3/llama.cpp code. Existing vessel behavior, SQLite
records, development mock and branches were preserved. No local model adapter is
claimed as implemented.

Added a local PDF/UTF-8 text library with originals, extracted chunks and a
transactionally maintained SQLite FTS5 index. Alembic migration 0002 upgrades the
existing schema without changing vessels. FastAPI dispatches to a consent-gated
workflow; provider contracts, OpenAI SDK integration, local retrieval and citation
validation have separate boundaries. The SDK uses structured chat outputs, a
backend environment key, allowlisted models, configurable timeout/retries,
`store=False`, sanitized errors and no provider fallback.

Authorized question translation supplies English/Vietnamese keywords for local
FTS5/BM25 retrieval without embeddings or llama.cpp. Generation receives at most
six 1,600-character chunks from the selected document. Exact quotes and excerpt
IDs are validated; page/title/document references are constructed locally.
Documents are untrusted data in user-message JSON, never system instructions.
There are no tool calls, document-triggered actions or vessel mutations.

The existing workspace now has Documents and AI Assistant views with local
import, provider/model status, explicit per-attempt consent, loading/error states,
answers and sources. Consent resets when inputs change and after submission.
Originals stay local; short documents may fit entirely in selected excerpts, as
disclosed before consent. Neither credentials nor automatic profile context are
sent to the browser/model.

## Configuration and reproduction

[README online setup](../README.md#online-document-questions) documents installation,
limits, migration, API routes and all environment variables. `OPENAI_API_KEY` is
required only for online inference. Optional variables: `OPENAI_MODEL`,
`OPENAI_MODELS`, `OPENAI_TIMEOUT_SECONDS`, `OPENAI_MAX_RETRIES`. Existing database
and origin variables remain supported. Set environment variables in the backend
process; `.env` is not auto-loaded. Start with `python scripts/dev.py` after
installing the updated lock file. No model download is required.

Automated verification from the indicated directories:

| Check | Result |
| --- | --- |
| backend: `python -m pytest -q` | 66 passed |
| frontend: `npm test` | 17 passed |
| frontend: `npm run build` | Passed, TypeScript + Vite production bundle |
| frontend: `MARITIME_E2E_SYNTHETIC=1 PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm run test:e2e` | 3 passed against an isolated synthetic SDK backend |
| Changed Python files: Ruff; Git whitespace check | Passed |
| `pip-audit -r backend/requirements-dev.lock --disable-pip --no-deps --cache-dir /tmp/maritime-audit-cache` | No known vulnerabilities found |
| frontend: `npm audit --json` (including dev dependencies) | 0 vulnerabilities |
| backend virtual environment: `python -m pip check` | No broken requirements |

The README includes the test-only `browser_app:create_e2e_app` startup commands.
Browser checks use actual HTTP, SQLite, FTS5 and citation checks; only the SDK
transport is mocked. The new browser case explicitly skips against the normal
backend unless its synthetic test flag is set. No paid API calls are needed.

Coverage includes provider initialization, missing key, authentication errors,
timeout and zero retry, malformed/declined structured output, Vietnamese questions
retrieving English evidence through mocked translation, cross-document isolation,
invalid/forged citations, missing evidence versus retrieval failure, strict consent,
input limits, PDF extraction, local storage/restart and the existing mock.
A regression upgrades a populated 0001 vessel database to 0002 and reads its vessel.

An additional disposable real-process smoke started the production app without an
API key or local model, migrated its database, created/edited/read a synthetic
vessel, imported a document, restarted Uvicorn, confirmed both persisted and
confirmed the consent gate. Chromium screenshots were reviewed for the document
answer on a 390px viewport. Mobile checks are emulation, not physical Android.
Windows CI has not run in this session. Existing Starlette TestClient emits one
httpx deprecation warning; tests pass.

## Known limitations

- **No live OpenAI verification.** No valid key is configured, and the environment
  network allowlist excludes `api.openai.com`. Mock transport verifies the official
  SDK contract, not real account/model access or answer quality.
- No Qwen3/llama.cpp implementation exists in this checkout. The legacy mock is
  preserved, and a local document adapter remains future work.
- Lexical retrieval plus query translation can miss synonyms, long-range context
  or tables; translation adds one API call, generation another when evidence is
  found. There is no semantic embedding index or recall guarantee.
- Exact quote/reference integrity does not prove claim entailment. Prompt
  instructions and no-action boundaries reduce injection impact but cannot
  establish that all malicious text will be ignored by a model.
- No OCR, scanned/encrypted PDF support, printed page-label interpretation,
  extraction preview, document deletion/edit/download API or chat history.
- Input/page/text limits bound stored data; the PDF parser runs in-process and is
  not a separate CPU/memory sandbox. Large complex PDFs may still be expensive.
- Existing single-user loopback model remains: no login, disk encryption or
  authentication against other local processes. Do not expose this backend.
- GitHub CLI reports its token invalid. No remote push/PR was performed; a local
  commit and a review-ready PR description are supplied.

## Recommended next task

After review, configure authorized OpenAI access and run a live smoke using only
synthetic documents and explicit consent. Benchmark Vietnamese/English retrieval
and claim/source accuracy, then add source previews and extraction review before
building human-reviewed form filling. Task 02 has not been started.

## Changed files

- `README.md`
- `backend/app/api/documents.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/app/models/document.py`
- `backend/app/schemas/document.py`
- `backend/app/services/citations.py`
- `backend/app/services/document_ai.py`
- `backend/app/services/document_workflow.py`
- `backend/app/services/documents.py`
- `backend/app/services/openai_provider.py`
- `backend/migrations/env.py`
- `backend/migrations/versions/0002_documents.py`
- `backend/pyproject.toml`
- `backend/requirements-dev.lock`
- `backend/tests/browser_app.py`
- `backend/tests/test_documents.py`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/ONLINE_API_ASSESSMENT.md`
- `docs/ONLINE_API_IMPLEMENTATION.md`
- `docs/ONLINE_API_PULL_REQUEST.md`
- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/ROADMAP.md`
- `docs/VALIDATION.md`
- `frontend/e2e/documents.spec.ts`
- `frontend/src/App.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/Documents.test.tsx`
- `frontend/src/Documents.tsx`
- `frontend/src/api.ts`
- `frontend/src/styles.css`
