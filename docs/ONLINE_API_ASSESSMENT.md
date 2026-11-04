# Task 01 architecture assessment (before implementation)

The supplied checkout is a vessel-profile foundation, not the document assistant
described in the task's assumptions. FastAPI routers use Pydantic schemas,
SQLAlchemy sessions and an Alembic-managed SQLite database. React uses relative
`/api` requests through Vite. Existing tests cover vessel validation, provenance,
origin checks and persistence. Required commands are Pytest, Vitest and Vite build;
Playwright covers the real profile workflow with a disposable database.

`services/ai.py` contains a small synchronous Protocol and a development mock.
There is no Qwen3/llama.cpp implementation, document library, PDF extractor,
FTS5 index, hybrid search or citation validator to preserve in this checkout.
Configuration uses a frozen environment-backed Settings dataclass. No AI secrets
are configured. Vessel schema and behavior will remain intact.

Incremental implementation: add document tables and FTS5 through Alembic, extract
PDF/text locally, introduce a document-specific provider Protocol alongside the
existing mock, and use the official OpenAI SDK with structured outputs. Retrieval
uses local FTS5 with authorized question translation for Vietnamese/English
cross-language search, without embeddings or local models. Only bounded excerpts
are passed to generation. The HTTP workflow enforces explicit per-request consent.
Sources are constructed from stored metadata and exact-match validated quotes.
No provider fallback, document tools or agent actions are enabled.
