# Product requirements — Task 01

Historical foundation scope. The approved AI-first Task 02 scope and acceptance
are documented in [TASK_02.md](TASK_02.md); this document is not the full product MVP definition.

## Users and problem

Deck Officers, Chief Officers and Masters need a reliable vessel record while connectivity is unavailable for long periods. Current workflows spread particulars across documents and spreadsheets. The product will consolidate operational information and later add local AI assistance, without making AI output authoritative.

## MVP scope

- Professional responsive English workspace with Dashboard and Ship Profile.
- Clearly planned states for Documents, AI Assistant, Equipment, Checklists and Settings.
- Create/read/edit one active profile in the UI; multiple independent records supported by the API/database.
- Identity: vessel/former names, IMO, MMSI, call sign, flag, registry port, type, class and build year.
- Dimensions: LOA, LBP, breadth/depth moulded and summer draft in metres.
- Tonnage: GT/NT (dimensionless integer indices), summer deadweight in tonnes.
- Machinery: main engine manufacturer/model and power in kW.
- Blank/unknown values stored as null. Identifiers stored as strings. Positive measurements accept at most three decimal places; GT/NT are integers. Display explicit units.
- Validate identifier formats, IMO check digit, year 1800–2100, numeric limits and net/gross and LBP/LOA consistency, including partial updates.
- Field provenance: method, optional source reference, unverified/verified status and server timestamp. User changes reset verification. AI extraction cannot set verified. Explicit human verification is API-only in this foundation.
- Minimal mock AI provider interface, no expert answers or downloaded models.

## Non-functional requirements

Local operation on a Windows laptop with 16 GB RAM and CPU only; no cloud service or GPU needed. Lightweight SQLite and processes, no containers or message broker. Browser frontend assets available locally after install; no telemetry. Use loopback listeners, local CORS, validated JSON writes and no arbitrary filesystem API. Modular separation, migrations and automated tests support future extension. Initial dependency installation requires Internet; offline dependency distribution is future packaging work. Local data is not encrypted by the application.

## Acceptance

Frontend and backend start, migrations initialize SQLite, form creation and edits persist, Dashboard reads saved values, unknowns remain unknown, error feedback identifies invalid fields, and restarting the backend retains values. Backend tests, frontend tests and production build pass. CI covers Windows and Ubuntu. Browser smoke exercises real persistence and mobile layout where available. Required docs, feature branch and committed changes are present. Do not download models, require API keys, commit real data or implement Task 02 automatically.

## Outside Task 01

Document extraction, certificate expiry, maritime knowledge base, checklists, report generation, email drafting, real AI inference, plugins, authentication, multi-user access and desktop installers are future work. This is a development foundation, not a certified navigation or safety-critical system.
