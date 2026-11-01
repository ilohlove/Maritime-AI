# Extraction foundation

Base: Task 02 `c0062e9`. Branch: `feature/extraction-foundation`.
This is an internal representation/migration change. **PDF remains the only
supported user import.** No new dependencies, file-format extractors, OCR,
provider changes, Ship Profile changes, public deployment or main merge.

## Common contract

`Extractor.extract(ExtractionFile) -> ExtractionResult` lives in
`backend/app/schemas/extraction.py`. The input carries a trusted local path and
application-assigned document/revision metadata. The result contains immutable
Pydantic records for metadata, units, typed locators, optional table content,
status (`ready`, `partial`, `failed`), extraction errors and extractor identifier.

Metadata distinguishes technical revision UUID, content SHA-256 and nullable
business version/effective date. Those business fields are not inferred from a
hash, filename, PDF modification timestamp or an import timestamp. One import
currently creates one immutable document/revision pair; importing identical bytes
again creates another pair, not an overwrite. There is no revision-editing,
version-grouping or historical-version picker feature in this task.

Locator variants: PDF page, section/paragraph, sheet/cell-range, row range, line
range and image/optional pixel region. These are typed contracts, not additional
import capabilities. `ContentUnit` carries source text and, for table units,
column labels and a rectangular matrix of string/null cells. Future extractors
must supply source-faithful text for indexing/quoting alongside the structured
table; the current PDF extractor does not recognize tables or add OCR.

The PDF worker conforms to the same contract and retains its subprocess timeout,
page/size/text limits and Linux memory limit. Empty pages are preserved as empty
units with warnings (`partial` when some other pages have text); a wholly
unreadable/scanned PDF fails. Worker metadata must match the original input.
Ready/partial status and errors are stored with the revision. Failed imports
retain the existing behavior: HTTP error, new temporary file removed, no indexed
record. A persistent failed-import history is not implemented.

## Migration 0003 and data preservation

Adds `document_revisions` and `content_units`. Existing PDF documents receive a
deterministic initial revision UUID; each real legacy page receives a deterministic
unit UUID. Existing document IDs, original files, SHA values, timestamps, page
text, chunk IDs (`E42` stays `E42`), excerpts and FTS rows remain unchanged.
Business version/effective date remain NULL. Legacy extractor version remains
unknown (NULL); no re-extraction or fabricated source location occurs.

The chunk table gains revision/unit references; the PDF-only `page_number`
column becomes nullable using Alembic's SQLite batch table copy. No re-chunking
or FTS rebuild takes place. SQLite foreign keys retain references and migration
tests check `PRAGMA foreign_key_check`. New writes reference real unit/revision
rows. The legacy pages table is retained for compatibility/migration reversibility;
new PDF writes populate it as well. Normal source inspection reads common units.
The legacy `documents.page_count` remains a count of PDF page units; for internal
non-page contract fixtures it is zero, and no fake page locator is generated.

Downgrade permits faithfully representable migrated legacy PDFs only. It refuses
new extraction metadata/non-page sources rather than silently discarding them.
Before upgrading any operational database, stop the application and copy the
SQLite file **and its documents directory** together. No operational data was
used or modified during implementation/testing.

## Retrieval and source inspection

FTS5 normalization, query terms, BM25 ranking, top-three limit and 700-character
windows/500-character stride are unchanged. Storage iterates content units rather
than assuming each string is a page. Retrieval joins each chunk to its unit and
revision, returning `revision_id`, `unit_id`, `source_format` and typed `locator`.
PDF `page_number` remains an additive compatibility field; non-page fixtures
return NULL for that field.

The LLM provider file is unchanged. It still receives evidence IDs/excerpts and
returns IDs/quotes; the backend continues validating those quotes. Names,
revision identity, unit identity and locations come from storage, not the model.
The frontend formats typed locators and resolves:

`GET /api/documents/{document_id}/revisions/{revision_id}/units/{unit_id}`

The endpoint checks the full document/revision/unit association, returning 404
for mismatched references. The existing PDF `/pages/{page_number}` endpoint
keeps its previous fields and adds revision/unit/locator metadata. Original PDF
download remains compatible. The generic source response also exposes table
content when supplied by an internal contract fixture; this is not a table import UI.

No AI Workspace redesign: the same citation card/button and source-text area are
used. A page locator still says “Page 1”; a sheet locator says “Sheet Safety ·
B2:C3”, without inventing a page number. The source area's accessible name is
now “Source content”. Source identity/quote validation does not prove semantic
entailment or real-model quality.

## Validation

Commands (backend virtual environment active):

```sh
cd backend
python -m pytest -q
cd ../frontend
npm test
npm run build
npm run test:e2e
```

Browser tests require a disposable migrated backend, as documented in Task 02.
This session uses backend `127.0.0.1:8003`, frontend `127.0.0.1:5176`, and isolated
`/tmp/extraction-foundation-e2e/data.db`; temporary runner/proxy configuration is
outside tracked application files. Default preview remains
`python scripts/synthetic_preview.py` with frontend port 5173.

Tests cover PDF extraction/import, blank-page status/errors, stable identities,
legacy-data migration and reversible preservation, exact source resolution,
wrong-revision rejection, quotes, typed locators, table contract persistence and
unsupported-format rejection. Non-PDF test records are constructed directly to
exercise the internal contract; no non-PDF parser/import was implemented.
Existing Ship Profile regression, local adapter and browser tests are retained.
Fresh execution results and the exact changed-file list are recorded below.

## Limits

Only PDF parsing and the existing PDF UI/import validation are supported. Locator
variants and table representations are foundations for later approved extractors.
There is no OCR, automatic table recognition, semantic retrieval, version editor
or new service. No real LLM inference, Windows hardware test, physical Android
test or remote CI execution is claimed by this refactor. Browser answer-display
checks continue to use an explicitly labeled deterministic response fixture.

## Fresh results (Linux, Python 3.12, Node 24, Chromium)

- Backend: **64 passed**, including migrated legacy PDFs, unchanged FTS/chunk IDs,
  cross-document/revision/unit rejection, quote checks and Ship Profile regression.
- Frontend: **17 passed**, including typed locator labels and exact source URLs.
- TypeScript/production build: **passed**.
- Existing Playwright suite: **3 passed**, against the isolated synthetic backend.
- One existing upstream Starlette/httpx TestClient deprecation warning remains.
- Not executed: real LLM inference, physical Windows/Android acceptance, remote CI.
  These are not claimed as verified. No new dependency was introduced.

## Exact changed files

```text
README.md
backend/app/api/workspace.py
backend/app/schemas/extraction.py
backend/app/services/documents.py
backend/app/services/pdf_worker.py
backend/migrations/versions/0003_extraction_units.py
backend/tests/test_extraction.py
backend/tests/test_workspace.py
docs/ARCHITECTURE.md
docs/EXTRACTION_FOUNDATION.md
frontend/e2e/ai-workspace.spec.ts
frontend/src/AIWorkspace.test.tsx
frontend/src/AIWorkspace.tsx
frontend/src/sourceLocator.test.tsx
frontend/src/sourceLocator.ts
```
