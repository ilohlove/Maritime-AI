# Architectural decisions

1. **Local browser monorepo:** React/Vite and Python/FastAPI are independently testable and portable to a future desktop shell. No container or cloud infrastructure is necessary.
2. **SQLAlchemy + SQLite + Alembic:** a single local file is sufficient for a single officer; explicit versioned migrations prevent implicit schema drift. Production-grade backup/encryption require later work.
3. **UUID records; first profile in UI:** supports multiple records without a premature fleet-management UI. API IDs prevent a singleton table migration later.
4. **Nullable values and decimal boundaries:** unknown is null, not zero or invented content. Dimensions/draft use m, deadweight t, power kW. Three decimal places and bounded magnitude keep values predictable; SQLite native NUMERIC limitations are documented. GT and NT are integer indices.
5. **Per-field JSON provenance:** a small, inspectable mapping prepares extraction without an entity-attribute-value model. PATCH preserves untouched sources and resets changed data to unverified. Current-state metadata is not audit history.
6. **Local Only document inference (Task 02):** extend the provider boundary with typed grounded answers and an owned CPU-only llama.cpp process. Configure a local GGUF explicitly; missing models fail clearly. No external provider, fallback or model weights in Git. Legacy mocks remain test-only. Exact citation IDs/quotes are checked before display; real model quality and Windows hardware acceptance require separate evidence.
7. **Relative API and loopback:** frontend proxy avoids hard-coded remote URLs. Explicit CORS, Origin checking for writes and JSON content types protect the local browser workflow; no claim of local-process isolation or network server security.
8. **Test layers:** Pytest against temporary migrated SQLite proves persistence; Vitest exercises controls/errors; Playwright optionally exercises real services. CI includes Windows and Ubuntu, tests and build. No real vessel fixtures.
9. **System fonts and CSS:** responsive design and simple theme variables avoid UI framework weight and network fonts. English copy has a starting localization boundary, not a full translation subsystem.
10. **No automatic next milestone:** Task 02 was explicitly approved for implementation; later form-filling work still requires review and approval.
