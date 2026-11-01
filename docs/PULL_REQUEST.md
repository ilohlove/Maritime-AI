# Task 01: initialize offline maritime workspace and vessel profiles

This initial foundation gives officers a local vessel record: create or edit particulars in Ship Profile, then view the stored vessel on Dashboard. SQLite retains records across application restarts. The React workspace is responsive, supports light/dark themes and labels all other modules Coming Soon.

FastAPI/Pydantic validates identifiers, decimal precision and related dimensions/tonnage. UUID-based vessel rows support future multi-vessel selection; field provenance tracks source, method, verification and server timestamps. Changed data is unverified by default. AI remains an explicit mock without models or external calls.

Includes Alembic migrations, a cross-platform development launcher, pinned dependencies, Windows/Ubuntu CI and product/architecture/engineering documentation. Services bind to loopback with restricted origins and JSON-only writes.

Validation:

- Pytest: 29 passed, including migrations, provenance and SQLite restart persistence.
- Vitest: 7 passed.
- TypeScript and Vite production build passed.
- Playwright/Chromium: 1 real-service smoke passed, covering create/edit/reload and mobile layout.
- Actual service restart retained synthetic test records and decimal values.
- npm audit and backend lockfile audit found no known vulnerabilities after patch upgrades.

Limitations: Windows CI has not executed here. The UI uses the first vessel; verification UI, immutable audit history, backups, encryption and authentication are future work. No real vessel data or models are included. Review Task 01 before authorizing Task 02.
