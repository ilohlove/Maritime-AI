# Architecture

## Runtime and communication

React + TypeScript runs in a local browser. Vite serves assets and proxies same-origin `/api` requests to FastAPI on 127.0.0.1:8000. FastAPI calls profile services, Pydantic validates boundary data, SQLAlchemy stores SQLite records. Alembic performs explicit migrations before startup; application import never creates tables. `GET /api/health` queries the schema, so missing migrations fail readiness.

```text
Local browser → Vite / bundled frontend → /api → FastAPI
                                                 ↓
                                        Profile service
                                                 ↓
                                        SQLAlchemy → SQLite
```

API: list/create `/api/vessels`, retrieve/patch `/api/vessels/{id}`, health `/api/health`. POST accepts optional particulars; PATCH only mutates supplied fields, merges existing values for cross-field validation and commits once. Omitted values retain data, explicit null clears it. A UUID identifies each profile. The MVP UI uses the earliest created profile, without inventing an `active` flag; a future vessel picker can select another ID. Lists are unpaginated in this small local MVP.

## Storage and provenance

A `vessels` table contains nullable typed particulars, UUID, created/updated timestamps and a JSON `field_provenance` map keyed by stable field names. Decimal SQLAlchemy Numeric(14,3) values avoid application-level float arithmetic; Pydantic serializes them as decimal strings and the UI submits strings. SQLite uses NUMERIC affinity internally (it is not a native fixed-point engine); the chosen limits and three-decimal quantization are covered by persistence tests. If future precision requirements increase, migrate to scaled integer storage. GT/NT are integers. IMO/MMSI remain strings.

Every non-null submitted field receives provenance: `extraction_method` (user_entered/imported/ai_extracted), `source_document` (logical reference only), `verification_status`, `last_updated`. A regular edit resets that field to user_entered/unverified; unchanged metadata survives PATCH. Clearing a value removes its provenance. Timestamps come from the server. AI-sourced verified submissions are rejected. A subsequent explicit human verification can resubmit the reviewed field as user_entered/verified. This is current-state provenance, not a document store or immutable audit history. A normalized event/document schema can follow when extraction exists.

## Extraction foundation update

Migration 0003 adds immutable source revision metadata and typed content units;
chunks reference their revision/unit and retrieval returns typed source locators.
FTS5 ranking/chunking and the LLM provider are unchanged. Existing PDF data,
evidence IDs and the PDF page API are preserved. The common source-inspection
endpoint resolves document/revision/unit together; frontend labels depend on the
locator type. Only PDF is importable. See [Extraction foundation](EXTRACTION_FOUNDATION.md)
for the contract, compatibility details, test evidence and known limitations.

## Task 02 document Q&A and local inference

AI Workspace is the primary screen; its status/loading is independent of the
optional vessel record. Knowledge & Files exposes the same selected-source workflow;
Dashboard and Ship Profile remain accessible. Tasks & Reminders is a placeholder.

`POST /api/documents?filename=...` accepts a bounded raw PDF body, stores a UUID-named
file, extracts text in a disposable parser process, and commits document metadata,
page text, overlapping chunks and FTS5 entries in migration 0002. Vessel schema is
unchanged. `GET /api/documents/{id}/pages/{page}` returns original extracted text;
`/file` downloads the original as an attachment. No arbitrary client paths are used.

`POST /api/questions` scopes retrieval to the selected document. Three lexical FTS5
excerpts feed `DocumentAIProvider.answer`. The production implementation owns a
loopback llama-server process with a configured local GGUF, GPU layers zero,
4096 context, 512 output tokens, one slot, offline flag and bounded wall time.
It speaks llama.cpp's schema-constrained chat-completions protocol, not a cloud API.
Explicit cancellation, disconnect or timeout cancels inference and stops the owned
runtime. Another request can reload it. No tool or vessel-mutation capability is
provided to the model. Online/Auto are rejected, not implemented as fallbacks.

Citations are accepted only for retrieved IDs and exact source quotes. Source name
and page come from the database, never the model. No matches or a model-declared
unsupported question returns insufficient evidence. Mechanical source validation
is not semantic entailment verification. Prompt injection remains a model-quality
risk, though the runtime has no application actions. FTS5 requires source-language
keyword overlap; it does not provide general cross-language semantic retrieval.

The original `AIProvider.respond`/MockAIProvider remain only as historical foundation
stubs for compatibility tests; the application does not route answers through them.
`skills/` remains notes, not an execution engine. See [Task 02](TASK_02.md) for
limits, configuration and unverified real-model/Windows acceptance.

## Offline and security boundary

Data, assets and processes stay on the device. There are no CDN assets, remote fonts, telemetry, API keys or external inference requests during normal operation. Separately installed local model weights are required for generated answers. Offline-first means a local service and locally served frontend, not a service-worker PWA. Dependency installation and eventual artifact distribution are separate concerns.

Loopback binding and explicit browser-origin write checks reduce exposure; CORS is restricted and JSON-only mutations reject form submissions. This is not multi-user security or local-process authentication. No secrets or operational data in Git. Database encryption, authenticated deployment, signed desktop builds, backups and audit history remain future security work. Windows operation uses standard Python/Node without Linux-only runtime dependencies.

## UI and localization

AI Workspace and Knowledge & Files share the implemented document workflow; Dashboard and Ship Profile remain functional supporting screens. Tasks & Reminders is explicitly unavailable. Shared field definitions supply labels/units and controls; stable field keys match API names. Domain/UI files and central `copy.ts` establish the English locale boundary; remaining component text will be extracted when a second locale is added. Theme preference alone is stored in browser localStorage; vessel data comes from SQLite. No client-side duplicate vessel database. State is in memory while editing; navigation before saving currently discards edits.
