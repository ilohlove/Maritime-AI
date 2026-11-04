# Add consent-gated online document QA to the existing maritime workspace

The current application only provides vessel profiles and a development AI mock.
This change adds local PDF/text import, SQLite FTS5 retrieval and document-scoped
OpenAI answers with exact validated source quotes. Vietnamese/English question
translation supports cross-language search without local models or embeddings.
Each online attempt requires explicit consent; only bounded retrieved text is
sent, credentials stay in the backend, and provider failures never trigger fallback.
Existing vessel persistence and the legacy mock remain intact. Migration 0002 adds
new tables/indexes without changing vessel records.

Validation: 66 backend tests, 17 frontend tests, production build and 3 Chromium
browser cases passed with disposable databases and mocked official-SDK transport.
A production-app process smoke verified startup without a key/local model and
persistence after restart. Dependency audits found no known vulnerabilities.
Windows/physical Android and live OpenAI account/model access were not verified.

See `docs/ONLINE_API_IMPLEMENTATION.md` for configuration, changed files and limits.
FTS5/query translation recall and model claim entailment still need evaluation;
OCR and local document inference adapters remain future work.

Target: feature/online-api-mvp. No merge or Task 02 is requested automatically.
