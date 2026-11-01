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

## AI and future skills

`AIProvider` is a minimal Python Protocol with `name` and `respond(prompt)`. Only `MockAIProvider` exists and returns a fixed development disclaimer without echoing private prompts or providing maritime advice. No AI endpoint is exposed. Future Ollama/llama.cpp adapters should add capability/timeout contracts only when needed, remain optional, and never automatically verify extracted particulars.

`skills/` currently contains design notes only. A future skill engine should register explicit, versioned skills with typed inputs/outputs and permission requirements. It must not evaluate arbitrary user code. Do not introduce a plugin loader, background job infrastructure or an inference runtime in Task 01.

## Offline and security boundary

Data, assets and processes stay on the device. There are no CDN assets, fonts, telemetry, models, API keys or external requests during normal operation. Offline-first means a local service and locally served frontend, not a service-worker PWA. Dependency installation and eventual artifact distribution are separate concerns.

Loopback binding and explicit browser-origin write checks reduce exposure; CORS is restricted and JSON-only mutations reject form submissions. This is not multi-user security or local-process authentication. No secrets or operational data in Git. Database encryption, authenticated deployment, signed desktop builds, backups and audit history remain future security work. Windows operation uses standard Python/Node without Linux-only runtime dependencies.

## UI and localization

Seven navigation modules, only two functional. Shared field definitions supply labels/units and controls; stable field keys match API names. Domain/UI files and central `copy.ts` establish the English locale boundary; remaining component text will be extracted when a second locale is added. Theme preference alone is stored in browser localStorage; vessel data comes from SQLite. No client-side duplicate vessel database. State is in memory while editing; navigation before saving currently discards edits.
