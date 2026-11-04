# Architecture

## Runtime and communication

React + TypeScript runs locally or as static GitHub Pages assets at `/Maritime-AI/`. API requests use a configured HTTPS backend origin for Pages or the relative dev/same-origin `/api` proxy. FastAPI calls profile services, Pydantic validates boundary data, SQLAlchemy stores SQLite records. Alembic performs explicit migrations before startup; application import never creates tables. `GET /api/health` queries the schema, so missing migrations fail readiness.

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

## AI and future skills

The original `AIProvider`/`MockAIProvider` remains intact. Document inference uses
`DocumentAIProvider` (`query_terms`, `answer`, `close`) and provider registrations
with explicit online metadata. `openai_provider.py` owns SDK response parsing,
secret access, timeouts, retries and sanitized errors. No SDK objects cross that
boundary. A local adapter can implement the same Protocol and register with
`online=False`; this checkout has no Qwen3/llama.cpp implementation.

HTTP routes only validate/dispatch. `document_workflow.py` enforces per-request
consent before provider creation and coordinates retrieval, inference and citation
validation, closing provider resources on both success and failure. No provider
fallback is configured. `documents.py` extracts PDF/text locally and searches
FTS5; `citations.py` checks exact quote membership and allowed excerpt IDs and
constructs document/page references from local metadata. Source contents never
become system messages or executable tools. Semantic entailment of model prose
is not guaranteed by citation integrity.

Migration 0002 adds `documents` (including original bytes), `document_chunks` and
an external-content FTS5 index with insert/update/delete triggers. Import is one
transaction. Unicode61 search removes diacritics and uses bounded OR keyword
queries ordered by BM25. An authorized OpenAI call translates the question to
English/Vietnamese terms before local retrieval. No embeddings or local inference
runtime is required. Six overlapping chunks of at most 1,600 characters bound
context to 9,600 characters. FTS/storage failures remain distinct from no matches.

Document API: `GET/POST /api/documents`, `GET /api/ai/providers`,
`POST /api/documents/{id}/questions`. Import uses bounded JSON/base64 under the
existing JSON-only Origin guard; there is no arbitrary filesystem path input.
Answer claims each contain a source with document UUID, local title, physical
page, chunk ID and exact quote. Neither original document bytes nor vessel profile
fields are supplied to OpenAI. Short documents may fit entirely in selected text.

`skills/` currently contains design notes only. A future skill engine should register explicit, versioned skills with typed inputs/outputs and permission requirements. It must not evaluate arbitrary user code. Do not introduce a plugin loader, background job infrastructure or an inference runtime in Task 01.

## Offline and security boundary

Local installations keep profiles/documents on the device; cloud configurations store them on the authenticated backend and its durable volumes. There are no CDN assets, remote fonts or telemetry. Online document questions send only the authorized question and bounded retrieved text through the OpenAI provider; credentials remain in the backend environment. Offline-first means a local service and locally served frontend, not a service-worker PWA. Dependency installation and eventual artifact distribution are separate concerns.

Loopback binding and explicit browser-origin write checks reduce exposure; CORS is restricted and JSON-only mutations reject form submissions. Owner authentication now protects private APIs; this is still not multi-user authorization or OS-process isolation. No secrets or operational data in Git. Authenticated cloud deployment is prepared and an operator backup tool is included; no deployment has occurred. Volume encryption is a hosting prerequisite; signed desktop builds and audit history remain future work. Windows operation uses standard Python/Node without Linux-only runtime dependencies.

## UI and localization

Seven navigation modules; Dashboard, Ship Profile, Documents and AI Assistant are functional. The latter two share a focused document workspace with provider configuration status, model selection, request-specific consent, loading/errors and validated sources. Shared field definitions supply labels/units and controls; stable field keys match API names. Domain/UI files and central `copy.ts` establish the English locale boundary; remaining component text will be extracted when a second locale is added. Theme preference alone is stored in browser localStorage; vessel data comes from SQLite. No client-side duplicate vessel database. State is in memory while editing; navigation before saving currently discards edits.

## Task 02A security and cloud boundaries

Private HTTP routes are deny-by-default behind opaque, expiring, revocable owner
sessions. Only login/health/CORS preflight is public; docs/OpenAPI are disabled.
`auth.py` owns scrypt verification, hashed durable sessions, persistent login/AI
rate windows and CSRF verification. Bearer tokens stay in frontend memory for
cross-site Pages; cookie mode requires same-origin hosting and HttpOnly/Secure/
SameSite=Strict plus CSRF. `AuthGate` handles login/logout and expiry/401 unmounts.

`ai_limits.py` reserves a conservative worst-case two-call token allowance with
SQLite immediate transactions and bounds process-wide concurrency. SDK requests
have a conservative byte-based input bound, separate translation/answer output
caps and zero retries. No inference starts if quota storage fails. Single-worker/
replica operation is required; token quota is not an exact monetary spend cap.

Migration 0003 adds sessions/rates/usage and a nullable original filename. New
originals are UUID files in a configurable private directory; legacy BLOB originals
remain compatible. SQLite stores extracted text and sources. Startup validates
schema/FTS/session tables, paths, referenced files and volume write access. The
operator must attest real durable storage; the app cannot prove a cloud mount.

`start_backend.py` fixes one worker and trusts only explicit proxy IP/CIDRs.
Production checks secrets, HTTPS origins, hosts and persistent storage; request
middleware enforces auth, origin, bounded JSON and HTTPS. Explicit CORS includes
credentials/Authorization/CSRF without wildcard origins. No deployment is performed.
See [operations and security trade-offs](CLOUD_DEPLOYMENT.md).
