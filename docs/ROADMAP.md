# Approved AI-first development sequence

1. **Task 01 — foundation:** implemented SQLite-backed Ship Profile and Dashboard,
   migrations, validation, provenance and tests. Supporting context, not the core product.
2. **Task 02 — AI Workspace + local document Q&A:** implementation delivered on
   `feature/task-02-ai-workspace`: text-PDF intake, page evidence, FTS5 retrieval,
   owned CPU-only llama.cpp adapter and source inspection. Deterministic checks
   pass; **real-model acceptance and Windows 16 GB performance remain UNVERIFIED**.
   Follow [Task 02 setup/acceptance](TASK_02.md). Do not equate test mocks with inference.
3. **Next proposed task — one reviewed form-filling workflow:** only after Task 02
   review/approval. Reuse cited document evidence and optional Ship Profile data;
   unresolved/conflicting fields stay explicit; human review before export.
   Not implemented or automatically authorized by Task 02.
4. **Validate the combined functional MVP offline on Windows:** actual model,
   understanding, referenced retrieval, reviewed form output, restart persistence,
   memory/latency and a practical data recovery procedure.

The intended primary experience remains AI Workspace, Knowledge & Files, then
Tasks & Reminders. Report writing, translation, checklists and personal reminders
follow demonstrated officer needs after the initial workflow; they are not a
parallel ERP/equipment/fleet roadmap. No OCR, cloud providers, multi-agent engine,
reminder scheduling or automatic form filling is included in Task 02.

Each later milestone needs explicit approval. Do not merge into main automatically.
