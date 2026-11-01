# Task 02 validation

Baseline: reviewed `ede01a6`. Implementation branch: `feature/task-02-ai-workspace`.
Validation environment: Codex Cloud Linux, Python 3.12.14, Node 24.19.0,
system Chromium. All documents, questions and vessel fixtures are synthetic.

| Check | Result |
| --- | --- |
| Backend `python -m pytest -q` | 50 passed, including the existing Ship Profile suite. |
| Frontend `npm test` | 10 passed, including independent AI Workspace loading, import, citations and error states. |
| Frontend `npm run build` | TypeScript and production bundle passed. |
| Chromium `npm run test:e2e` | 3 passed: document workflow UI, desktop/mobile Ship Profile, Pixel 7 touch navigation/edit/save/reload. |
| Process/HTTP adapter integration | Passed using an explicit synthetic runtime subprocess, including CPU/offline flags, schema-constrained request, startup, cancellation and shutdown. This is not a real LLM. |
| PDF parser | Patched pypdf 6.21.4. Valid extraction, page identity, filename traversal containment, malformed/wrong/oversized files, scanned/empty PDFs, encryption and page count tested. |
| Retrieval/citations | FTS5 selected-document isolation, Vietnamese normalization, exact page excerpts, unsupported questions, fake IDs/quotes rejected, inference errors and missing model tested. Deterministic providers only. |
| Security | Existing cross-origin/JSON-write checks plus raw-PDF import origin/type checks and refusing an occupied model port passed. No online/auto mode accepted. |
| Restart | Full launcher stop/start retained the same document ID `27b593f1-4ee8-416d-9664-78715d41a73b` and vessel ID `1477d933-5921-40b1-bfc1-8d0537f6ef62`; backend tests separately check page persistence across app instances. |
| Dependency review | npm audit: zero vulnerabilities. pip-audit of pinned backend requirements via PyPI: no known vulnerabilities after upgrading the initially selected PDF parser to 6.21.4. Advisory evidence is dated, not a future guarantee. |
| Real local-model acceptance script | **UNVERIFIED**: exited with “Local model unavailable. Configure MARITIME_MODEL_PATH with an installed GGUF file.” No successful inference is claimed. |
| Real Qwen3-4B-Instruct-2507 inference | **UNVERIFIED**. No runtime/weights installed. Hugging Face model-download host was rejected by environment proxy with HTTP 403. |
| Physical Windows 16 GB CPU performance | **UNVERIFIED**; no target hardware was available and no model benchmark ran. |
| Physical Android and authenticated cloud preview | **UNVERIFIED**. Chromium emulation passed; there is no supported preview forwarding capability in this session. |

The successful-answer portion of the browser test stubs only the generation
response and labels it BROWSER TEST STUB. Upload, source page fetch, original
file and missing-model/unsupported responses use actual application routes.
Backend tests separately verify that invented citation IDs and non-verbatim
quotes are rejected. The runtime-process fixture is likewise labeled as a
protocol fixture and cannot be presented as Qwen inference.

Backend tests emit one upstream Starlette/httpx TestClient deprecation warning.
No Windows/remote CI result is claimed. Test success does not verify semantic
entailment, resistance of a real model to all prompt injection, general
multilingual retrieval, maritime correctness or memory/latency suitability.

The application was tested against disposable SQLite under
`/tmp/task02-browser-data`, separate from the retained synthetic preview database.
The Product Alignment Review was not modified. No real data, weights or runtime
binaries are committed. No public deployment, main merge, OCR, cloud provider,
form filling, reminders, fleet subsystem or multi-agent orchestration was added.

For exact install, run, phone-preview alternatives and real-model Windows
acceptance, follow [TASK_02.md](TASK_02.md). The remaining acceptance gate is
explicitly pending; the implementation is not certified as a fully verified AI
workflow until that real-model test succeeds and its output is reviewed.
