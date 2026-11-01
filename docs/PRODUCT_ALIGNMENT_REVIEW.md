# Product alignment review

Review date: 2026-11-01. Source baseline: `f1c31b3` on `feature/ui-preview`;
review branch: `feature/product-alignment-review`.

**Assessment:** retain the existing foundation. It is a small, working local
Ship Profile application, not yet a functional AI assistant MVP. The main
alignment problem is the vessel-first experience and development sequence,
not the technology stack. Redirect the next approved work toward a useful
document-and-evidence workflow without rewriting the app.

This review changes documentation only. No application functionality, database
schema, dependency, deployment, or Task 02 implementation is included. Nothing
is merged into main. Recommendations below require product approval.

## 1. Original product purpose

Maritime AI Assistant is an offline-first personal AI workspace for seafarers,
initially deck officers. It should help an officer understand documents, find
supported answers, prepare reports, fill forms, translate text, use checklists,
and manage reminders during daily work, including periods without Internet.

The intended primary experience is:

| Area | Purpose |
| --- | --- |
| AI Workspace | Start a work request, select relevant local material, inspect evidence, and review an answer or draft. This is the central experience. |
| Knowledge & Files | Supply and inspect the local sources used by the assistant. Storage and retrieval serve work requests. |
| Tasks & Reminders | Keep track of follow-up work; introduce only after the core document workflow proves useful. |

Ship Profile supplies reusable, structured context for these workflows, such as
vessel particulars in a form. It should remain accessible and editable without
being a prerequisite for asking a document question.

Success for the first functional MVP means demonstrating **AI-assisted document
understanding, retrieval with source references, and automatic form filling**.
A dashboard, a saved profile, a mock response, or a file browser alone does not
meet that definition. Vessel/fleet management, maritime ERP, and a general
document-management platform are outside this product direction.

The current [Task 01 requirements](PRODUCT_REQUIREMENTS.md) describe a narrower
foundation and call its profile scope an MVP. Interpret that as a Task 01
deliverable, not proof that the product MVP above exists. The user's current
product direction governs future work.

## 2. Current implementation status

### Evidence and status definitions

- **Implemented and verified:** source exists and the stated behavior has direct
  test or execution evidence. This does not imply validation on every platform.
- **Implemented but not verified:** code/configuration exists, but the relevant
  integration, environment, or acceptance scenario has not been demonstrated.
- **Planned but not implemented:** no functional workflow exists; names, design
  notes, mocks, or roadmap entries do not count as implementation.

Source inspected includes the React entry point, App, ShipProfile, API client,
field definitions, CSS, Vite configuration, all backend runtime modules, the
migration, launchers, automated tests, and CI configuration. Documentation was
compared with code rather than used as a substitute for it.

| Capability | Status | Evidence and limits |
| --- | --- | --- |
| Dashboard and editable Ship Profile | Implemented and verified on Linux/Chromium | `frontend/src/App.tsx`, `ShipProfile.tsx`; unit and real-browser tests. Dashboard reads saved API data. |
| SQLite create/read/patch and restart persistence | Implemented and verified | `backend/app/api/vessels.py`, `services/vessels.py`, migrated temporary SQLite tests, including application restart. Previous preview preparation also verified full service restart. |
| Nullable fields, units, identifier validation, partial updates | Implemented and verified for tested cases | Pydantic schemas, frontend controls, backend validation and merged-PATCH tests. Identifier format/checksum is not proof of registration. |
| Current-state field provenance | Implemented and verified at API level | Tests cover untouched-field preservation, reset on ordinary edits, clearing, import metadata, and rejection of `ai_extracted` plus `verified`. It is not audit history. |
| Explicit verification submission | Implemented and verified at API level only | API accepts reviewed values with verification metadata; no human-verification UI or independent proof of human review exists. |
| Multiple independent profile records | Implemented and verified at API/database level | Distinct IDs tested. UI always takes the earliest profile; selection is not implemented. |
| AI Provider protocol and mock | Implemented and verified as a stub only | `backend/app/services/ai.py` defines `name` and `respond(prompt)`. Test checks the fixed disclaimer. No model execution occurs. |
| AI Assistant, Documents, Equipment, Checklists, Settings screens | Implemented and verified as placeholders only | `copy.ts` lists them; `App.tsx` renders Coming Soon. No corresponding work tools exist. |
| Local runtime without remote browser resources | Implemented and verified within the limited checks below | Relative API calls, system fonts and local assets; browser load with external HTTP requests blocked succeeded. Not a complete disconnected-device acceptance test. |
| Windows CI configuration | Implemented but not verified in this review | `.github/workflows/ci.yml` contains Windows/Ubuntu jobs. No remote CI result or physical Windows execution was obtained. |
| Phone/LAN and exact-origin cloud-preview configuration | Implemented but not verified on a physical phone or authenticated cloud preview | `scripts/synthetic_preview.py` supports an explicit origin and frontend bind address. Prior Chromium Pixel 7 tests are emulation. |
| 16 GB Windows CPU-only AI operation | Planned but not implemented | No inference adapter, model, or hardware benchmark. Current foundation running on Linux does not establish future AI feasibility. |
| Document ingestion, extraction, retrieval, citations, form filling | Planned but not implemented | No document API, file/source storage model, retrieval pipeline, generation endpoint, or template/export workflow. |
| Reports, translation, tasks and reminders | Planned but not implemented | No functional flows, persistence, or scheduling. |

### Frontend architecture

[`App.tsx`](../frontend/src/App.tsx) uses React state to switch modules and loads
`listVessels()[0]` on startup. [`ShipProfile.tsx`](../frontend/src/ShipProfile.tsx)
owns form values, dirty fields, validation and save feedback. A small fetch
wrapper sends relative `/api` requests; Vite proxies them to FastAPI. Theme
preference alone uses localStorage. Vessel records live in SQLite, not a second
browser database. React/TypeScript, CSS and system fonts are sufficient here;
there is no need for a router, state framework, design system, or desktop rewrite
just to begin the first AI workflow.

The shell currently makes vessel data the entire app's loading/error gate.
Dashboard is the default view, the brand says “Vessel Operations Workspace,”
and five of seven navigation destinations have no functional content. This
emphasizes vessel management and fragments the future assistant. When the AI
workflow is approved, give it its own loading/error state so an absent or failed
profile does not block document work. Preserve the existing profile component
and dashboard access while changing their prominence deliberately.

### Backend architecture

[`main.py`](../backend/app/main.py) builds the FastAPI app, engine/session
factory, CORS and JSON-write guard. Routers handle HTTP; the vessel service
merges and validates changes before committing; Pydantic handles input rules;
SQLAlchemy handles persistence. Alembic initializes the schema before launch.
The health endpoint queries the vessel table, so it checks schema availability,
not AI readiness. Its `ai_provider` value is a hard-coded mock label, not a
provider health probe.

This separation is proportionate. Keep one local backend process. The AI
protocol is not injected into the application or called by an endpoint; there
is no provider selection, inference lifecycle, timeout, cancellation, structured
result, or citation contract. It is a useful boundary to retain, not a completed
AI architecture. Extend it only with the first real use case. CPU inference
must not block the backend's event loop; a bounded worker or separately running
local model process can address that when measured, without a job broker.

### Database and Ship Profile

[`Vessel`](../backend/app/models/vessel.py) and
[`0001_vessels.py`](../backend/migrations/versions/0001_vessels.py) define one
domain table, plus Alembic's version bookkeeping. Nullable typed particulars,
UUIDs, timestamps and per-field JSON provenance are appropriate for small local
records. Preserve strings for identifiers and explicit null for unknowns.
Decimal strings at the API and three-place validation avoid frontend float
rounding, but SQLite NUMERIC affinity is not native fixed-point storage.
Current tests demonstrate selected values, not exhaustive numeric-boundary
accuracy. No precision-driven migration is justified by this review.

`source_document` is currently a free-text logical reference, not a foreign key,
stored document, page location, or retrievable evidence. JSON provenance records
the latest state only. Human verification currently resubmits a value with
metadata; it can replace the original extraction attribution and does not
establish who reviewed the source. Keep this honest distinction before using
provenance as the basis of AI citations. Add only the minimal document/evidence
storage required by an approved workflow; do not remodel the vessel table now.

### Offline readiness and resources

The current profile workflow has no cloud SDK, remote inference call, telemetry,
CDN font, or document transmission in application source. Assets are served
locally after installation. Python and Node dependencies initially require a
network connection; no offline installer, bundled dependency/model distribution,
or service-worker/PWA startup exists. A phone does not hold a standalone copy;
it needs the computer serving the UI and backend.

The reviewed build emitted about 203 kB of JavaScript and 5.72 kB of CSS before
compression. This supports keeping the UI simple, but says nothing about model
RAM or speed. No current inference resource measurement exists. For the eventual
16 GB Windows laptop, evaluate one small quantized model at a time, bound context
and document batches, and avoid concurrent large model/embedding loads. Keep
model/runtime choice behind an adapter; do not make an external account required.

Before accepting AI hardware support, measure total application/model/browser
peak memory, available OS headroom, cold start, time to first output, completed
answer time and extraction/retrieval time on a declared CPU and corpus. A small
context and a few short synthetic documents are the initial test workload.
Do not declare a model size, latency promise, or “fits in 16 GB” from weight
size alone: runtime buffers, context cache, indexing and Windows also use RAM.

### Security

Loopback defaults, explicit allowed origins, JSON-only writes, input limits,
unknown-field rejection and normal React text rendering are useful existing
protections. Security tests cover blocked cross-origin writes and form content
types. No current application route reads arbitrary paths or executes tools.

The boundary is a trusted single-user local machine. Requests without Origin
can write; CORS is not authentication. There is no login, local-process
isolation, database encryption, immutable audit, backup/restore interface, or
optimistic concurrency control. Simultaneous edits to the same field can
overwrite each other. LAN preview exposes synthetic data and an unauthenticated
development frontend; it is not an operational network deployment design.

For the first approved document workflow, bound file size/type and parsing cost,
store files under an application-owned directory with generated identifiers,
and treat filenames, extracted text and retrieved instructions as untrusted.
Document content must not authorize model tool execution, remote transmission,
or automatic profile changes. Require human review of extracted facts and form
output. These are future workflow requirements, not implemented protections.

### Automated tests and fresh evidence

On this review's Linux environment (Python 3.12.14, Node 24.19.0):

| Check rerun during this review | Result |
| --- | --- |
| Backend `python -m pytest -q` | 29 passed; one upstream Starlette/httpx TestClient deprecation warning. |
| Frontend `npm test` | 7 passed. Fetch is mocked here; these tests alone do not establish backend communication. |
| Frontend `npm run build` | TypeScript check and production bundle passed. |
| Existing two Playwright tests against a separate migrated SQLite backend | 2 passed; Chromium covers desktop and Pixel 7 touch emulation. |
| Browser Dashboard and Ship Profile load with non-loopback HTTP requests blocked | Passed; zero attempted external HTTP requests in that scenario. No edit was made to the retained preview profile. |

The isolated browser run uses backend port 8001, frontend port 5174, exact allowed
origin `http://127.0.0.1:5174`, and `/tmp/maritime-alignment-db/review.db`.
Temporary runner configurations live under ignored `frontend/node_modules/.cache`;
they are test orchestration, not application changes. This avoids modifying the
retained synthetic preview database.

Backend tests cover migration repeatability, rejected writes, cross-field
validation, provenance and SQLite persistence across app instances. Browser
tests exercise actual API saves and reloads, and mobile input validation.
They do not test AI quality, citation correctness, extraction, filling, model
availability, Windows inference, physical Android, or full offline distribution.
Playwright is not included in current CI jobs and can reuse an existing server
in the default configuration: it must be pointed at disposable synthetic data.

Historical [validation](VALIDATION.md) and [preview evidence](PREVIEW.md) remain
useful, but their older test counts and dependency-audit results are dated
observations. Package advisories were not re-audited during this documentation
review. Configured Windows CI is not a passing Windows test result.

## 3. What should be retained

- React/TypeScript, FastAPI, SQLite, SQLAlchemy, Alembic and the small monorepo.
  They support a local assistant without cloud infrastructure or a rewrite.
- The working Ship Profile form, Dashboard, API, units and validation. Use them
  as supporting structured context and regression coverage for later workflows.
- Unknown-as-null, changed-field PATCH semantics and unverified defaults. Never
  silently replace reviewed particulars with model output.
- The small AI provider boundary and explicit mock disclaimer. Keep private
  prompts/documents out of logs and avoid presenting the mock as a working model.
- Local assets, loopback defaults, explicit origins, synthetic fixtures, isolated
  preview database, migration discipline and layered tests.

## 4. What should be simplified

There is no current enterprise framework or service sprawl to remove. Simplify
the product's emphasis and intended sequencing first.

| Finding | Recommendation for later approved work |
| --- | --- |
| Seven equal navigation destinations; vessel-first entry | Move toward AI Workspace, Knowledge & Files, and Tasks & Reminders. Keep existing profile/dashboard accessible as supporting tools; no removal in this review. |
| Roadmap proposes vessel verification/audit/selection/backup before AI | Reprioritize the first evidence-backed AI workflow. Address a backup or data-integrity issue when it blocks that workflow, rather than building a vessel-management subsystem first. |
| API supports many profiles; UI silently chooses the first | Document this limitation and avoid building a fleet picker unless an officer workflow needs it. Do not delete records or impose a singleton migration. |
| App state and global loading depend entirely on vessels | Separate AI workflow state when adding it; avoid a global state framework until shared state actually warrants one. |
| Unsaved form data is component state | Navigation/reload discards unsaved input; save-failure retention applies only while the form stays mounted. Add a focused warning/draft strategy when this becomes a workflow blocker. |
| `Vessel` uses an open `unknown` index signature; field rules repeat across layers | Tighten field typing as integration grows and test rule parity. Backend validation stays authoritative; no schema-generation framework is required now. |
| Future “skills” and model adapters are mostly design notes | Defer plugin loading, agents, generic tool registries and universal provider capabilities. Implement only the operations the approved workflow needs. |

Do not add Kubernetes, containers as an end-user requirement, Redis, a message
broker, a separate vector database, microservices, tenancy or an event-sourcing
system for this MVP. A local file store and SQLite-backed evidence/search are
reasonable first candidates; semantic indexing must earn its resource cost.

## 5. What is missing

All items here are **planned but not implemented**:

1. A usable AI Workspace with a work request, selected sources, result and
   explicit unavailable-model/error states.
2. Controlled local document intake, text extraction, stable source identity,
   page/section evidence locations and source inspection.
3. Retrieval that returns inspectable excerpts and references; grounded answers
   must distinguish unsupported questions from supported facts.
4. One real local inference adapter with bounded requests, lifecycle/error
   handling and hardware/quality evidence. The mock is insufficient for this gate.
5. A form template, mapping of supported facts into fields, unresolved-field
   handling, review and export. Ship Profile can supply context; it is not form filling.
6. Offline installation/model distribution, recovery and physical Windows CPU
   acceptance. These are release concerns, not reasons to replace the current stack.

Report drafting, translation, checklists and reminders remain part of the stated
purpose, but should follow the first three MVP demonstrations rather than become
parallel modules now.

## 6. Risks of product scope drift

| Risk and concrete signal | Product control |
| --- | --- |
| Vessel management becomes the product: default Dashboard, vessel-centric copy, proposed profile-hardening milestone | Judge the next increment by an officer's document work completed, not fields, dashboards or vessel CRUD added. |
| Traditional ERP grows from Equipment, certificates, inspections and many records | Defer lifecycle management and fleet features. Add a narrowly scoped reminder only when the personal workflow needs it. |
| Document storage substitutes for assistance | Every supported intake path must feed a concrete question, explanation or form result with inspectable evidence. |
| Generic chat substitutes for grounded work | Require source references, missing-evidence behavior and a reviewed usable output in acceptance tests. |
| Model/runtime infrastructure consumes the roadmap | Evaluate one optional local runtime behind the existing boundary; no model catalog, agent platform, or multi-provider matrix first. |
| Polished placeholders and passing CRUD tests are called an AI MVP | Track implemented/verified status per workflow and require a real local model for AI acceptance. |
| A Linux development preview is called offline Windows readiness | Gate that claim on disconnected Windows operation, model availability, memory and latency measurements. |

The existing [ROADMAP.md](ROADMAP.md) and Task 01 product language contain these
signals. This review recommends replacing their future ordering after approval;
it does not silently change those documents or broaden current authorization.

## 7. Recommended next development task

**Proposed next task, awaiting approval: “AI Workspace — one local document,
one supported answer, visible source evidence.”** This is a recommendation,
not the start of Task 02.

Build one small vertical workflow using the current app: import a short synthetic
text-based PDF, extract page text locally, ask a document-specific question,
retrieve relevant excerpts, and produce a bounded answer through one optional
local model adapter. Show clickable source/page references and the exact excerpts.
Give AI Workspace the primary entry point while preserving access to the current
profile. Knowledge & Files should provide only the source controls needed here.

Keep it to one input format and one active document initially. Defer scanned-PDF
OCR, DOCX/Excel breadth, general agents, fleet functions, reminders, bulk ingest
and semantic infrastructure unless the acceptance case proves they are necessary.
Add a small document/evidence migration only when its persisted workflow is
defined; do not pre-build a universal knowledge schema or modify vessel storage.

Acceptance proposed for that task:

- On an installed local system without Internet, import a synthetic PDF and ask
  a supported question; show an answer with source/page/excerpt that the user can inspect.
- Ask an unsupported question and receive an explicit insufficient-evidence
  response rather than invented particulars. Validate that every displayed
  citation resolves to the imported source and actually supports its claim.
- Missing/unavailable model, malformed/oversized file and inference failure have
  clear outcomes; input documents and existing Ship Profile data remain intact.
- No model-driven action changes vessel data or marks extracted facts verified.
- Tests use synthetic fixtures. A mock may test wiring, but acceptance of
  AI-assisted understanding needs a real local adapter and reviewed answers.
- Benchmark the selected adapter on the target Windows 16 GB CPU-only hardware
  before claiming support. If hardware is unavailable, report that gate as
  unverified and keep the milestone pending, rather than substituting Linux results.

This increment demonstrates the first two MVP priorities on a narrow case.
It is not the complete MVP; automatic form filling is the following required slice.

## 8. Minimal implementation roadmap

Every step below is proposed and unimplemented. No dates, implementation
authorization, or model-performance guarantees are implied.

| Order | Deliverable | Completion evidence |
| --- | --- | --- |
| 0 | Approve alignment and next task | User reviews this report and the working profile preview. No code work until approved. |
| 1 | Document understanding and referenced answer in AI Workspace | The narrow workflow and acceptance gates in section 7, including real local inference evidence and retained Ship Profile regression checks. |
| 2 | One automatic form-filling workflow | A single agreed template is populated from cited document facts and optional Ship Profile data. Unknown/conflicting values stay unresolved; officer reviews values and evidence before export. Compare exported fields with synthetic expected values. This completes the third MVP priority. |
| 3 | Validate the combined functional MVP for offline use | Repeat import → question → evidence → fill → review/export on a disconnected Windows 16 GB CPU laptop after restart. Record memory/latency and reviewed answer/form quality. Prove a simple backup/restore procedure before operational records are entrusted to it; use existing OS file protection initially. |

After those gates, choose the next daily workflow from actual officer feedback.
Do not automatically start report generation, translation, Tasks & Reminders,
installer development, or multiple document formats in parallel. The eventual
three-area navigation does not require building every area for the first slice.

## 9. Instructions for previewing and testing the current application

### Start the synthetic preview

Requirements: Python 3.11+, Node 22.12+, npm. From the repository root:

```sh
python -m venv .venv
```

Activate with `source .venv/bin/activate` on Linux/macOS, or
`.venv\Scripts\Activate.ps1` on Windows PowerShell, then:

```sh
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
npm --prefix frontend ci
python scripts/synthetic_preview.py
```

In this managed sandbox, if npm's default cache is unwritable, use
`npm --prefix frontend ci --cache /tmp/maritime-npm-cache` instead. Preserve TLS
and package integrity checks. After installation the profile runtime uses local
assets and services; the install itself requires network access.

Open `http://127.0.0.1:5173` on the machine running the app. Backend is
`127.0.0.1:8000`. The launcher migrates and uses ignored
`.preview-synthetic/maritime.db`, overriding inherited operational database
settings. It seeds **SYNTHETIC PREVIEW VESSEL — TEST DATA** only when empty.
IMO and MMSI are blank; sample fields are unverified. Later saved edits persist
without being reset by launcher restart. Use synthetic data only.

1. Open Dashboard, then **View / edit ship profile** or **Ship Profile**.
2. Change a field to another synthetic value; choose **Save changes**.
3. Confirm **Ship profile saved locally.** and return to Dashboard.
4. Reload and reopen the profile to verify the change.
5. Stop with Ctrl+C, restart the same launcher and verify again.
6. Save before navigation: unsaved form state is not persistent.

### Android and cloud-preview limits

This session's tools provide no authenticated preview/port-forwarding facility;
the environment reports an empty capability list. There is no supported cloud
preview URL to give the phone. Cloud loopback is not the phone's loopback.
Nothing is publicly deployed. Previous real-UI captures are available in this
workspace under `/workspace/artifacts/` as `dashboard-android.png`,
`ship-profile-android.png`, `dashboard-android-dark.png`, and
`dashboard-desktop.png`; these are static visual evidence, not interactive access.

The simplest interactive alternative is a computer on the same trusted Wi-Fi
as the phone. Install/run the checkout there, substitute the computer's local
IPv4 address, and use:

```sh
python scripts/synthetic_preview.py --host 0.0.0.0 --origin http://192.168.1.20:5173
```

Open that exact address in Android Chrome. Allow frontend port 5173 through the
computer's private-network firewall if needed; do not configure router port
forwarding. The backend stays on loopback and Vite proxies its requests. This
explicit network bind is only for synthetic review; it is not appropriate for
real operational records. Stop both services with Ctrl+C.

If a future session supplies an authenticated cloud preview, use its exact HTTPS
origin with `--origin` and bind the frontend with `--host 0.0.0.0`; forward only
port 5173. The launcher cannot create such access. See [README](../README.md)
and [PREVIEW.md](PREVIEW.md) for the existing workflow.

### Repeat automated checks

With the backend environment active, from the repository root:

```sh
cd backend
python -m pytest -q
cd ../frontend
npm test
npm run build
```

For browser tests using the standard ports, first stop the preview. In a separate
backend terminal set `MARITIME_DATABASE_URL` to a **new disposable SQLite file**
with an existing parent directory; retain default local allowed origins. From
`backend`, run `python -m alembic upgrade head`, then
`python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000`.
From `frontend`, run `npx playwright install chromium` once if needed, then
`npm run test:e2e`. On this Linux environment, use
`PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium npm run test:e2e`.

Playwright starts Vite at port 5173 or reuses an existing Vite server. Its tests
create/edit the first profile, so never point it at real records or a retained
review profile. Stop the disposable backend afterward and restart the synthetic
launcher. The review's separate-port execution above demonstrates isolation
without stopping the retained preview.

**Decision pending:** approve or revise the proposed document-and-evidence task.
Task 02 remains unimplemented; no further development is started by this report.
