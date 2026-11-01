# Task 02: local document Q&A

Task 02 implementation starts from reviewed commit `ede01a6`. AI Workspace is
now the primary screen. Ship Profile and Dashboard remain accessible; neither
is required for document work. The Product Alignment Review remains unchanged.

**Real local-model acceptance: UNVERIFIED in Codex Cloud.** No llama-server or
GGUF was installed in the execution environment. A request to the Hugging Face
model download host was rejected by the environment proxy with HTTP 403. No
model was downloaded, no inference result was fabricated, and no model weights
are committed. Deterministic test providers and a protocol-test subprocess are
explicit test fixtures, not evidence of real AI execution. Physical Windows
16 GB CPU-only performance and physical Android operation are also UNVERIFIED.

## Implemented workflow

1. Import a text-based PDF in AI Workspace / Knowledge & Files.
2. Extraction runs in a disposable local parser process. Original PDF, extracted
   pages, chunks and document metadata are stored beside the SQLite database.
3. Choose an imported PDF and ask a question in Vietnamese or English.
4. SQLite FTS5 retrieves up to three overlapping, page-specific excerpts.
5. With a configured model, the application starts its own loopback llama.cpp
   server, CPU only, and requests a schema-constrained answer using the evidence.
6. The backend validates citation IDs and verbatim quotes against retrieved
   excerpts. The UI shows source name, page, quote, excerpt and full extracted
   page; the original PDF can be downloaded to inspect layout.
7. No retrieval matches, or a model-declared unsupported question, returns an
   explicit bilingual insufficient-evidence response. Invalid model output,
   invented citations, missing model and timeout are errors, not fabricated answers.

Only **Local Only** is implemented. Online and Auto are disabled. There is no
external provider URL, automatic fallback, OCR, form filling, reminder scheduler,
equipment/fleet management, tool execution or multi-agent orchestration.

## Install the application

Python 3.11+; Node 22.12+; CPU-only operation. From the repository root:

```sh
python -m venv .venv
```

Activate `.venv\Scripts\Activate.ps1` in Windows PowerShell, or
`source .venv/bin/activate` on Linux/macOS, then:

```sh
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps -e backend
npm --prefix frontend ci
```

Installation needs Internet. The installed application workflow does not require
Internet after the runtime and model are present. Download runtime/models on a
connected machine and transfer them to the offline laptop if necessary. Keep
weights, PDFs, private data and tools outside Git. A desktop/offline installer
is not included. SQLite must support FTS5 (standard Python distributions normally do).

## Windows: install a local runtime and model

The initial model candidate is **Qwen3-4B-Instruct-2507, GGUF Q4_K_M**. This is a
candidate, not a claim of measured suitability. Use a recent llama.cpp CPU
release supporting Qwen3 and the flags below. For Windows x64, run from the
repository root in PowerShell while connected to the Internet:

```powershell
$release = Invoke-RestMethod 'https://api.github.com/repos/ggml-org/llama.cpp/releases/latest'
$asset = $release.assets | Where-Object { $_.name -like '*bin-win-cpu-x64.zip' } | Select-Object -First 1
if (-not $asset) { throw 'No Windows x64 CPU ZIP in this release. Select a CPU build from the release page.' }
New-Item -ItemType Directory -Force .\tools\llama | Out-Null
Invoke-WebRequest $asset.browser_download_url -OutFile "$env:TEMP\maritime-llama-cpu.zip"
Expand-Archive "$env:TEMP\maritime-llama-cpu.zip" -DestinationPath .\tools\llama -Force
python -m pip install huggingface_hub
hf download unsloth/Qwen3-4B-Instruct-2507-GGUF --include '*Q4_K_M.gguf' --local-dir models
$runtime = Get-ChildItem .\tools\llama -Filter llama-server.exe -Recurse | Select-Object -First 1
$model = Get-ChildItem .\models -Filter '*Q4_K_M.gguf' -Recurse | Select-Object -First 1
if (-not $runtime -or -not $model) { throw 'Runtime or GGUF missing. Check the selected release and model repository.' }
$env:MARITIME_LLAMA_SERVER = $runtime.FullName
$env:MARITIME_MODEL_PATH = $model.FullName
$env:MARITIME_INFERENCE_TIMEOUT = '180'
$env:MARITIME_MODEL_PORT = '8081'
& $env:MARITIME_LLAMA_SERVER --version
Get-FileHash $env:MARITIME_MODEL_PATH -Algorithm SHA256
python scripts/synthetic_preview.py
```

The model repository above is a third-party GGUF conversion candidate, not an
application service. Its current availability/file list could not be verified
from this restricted cloud session. If the command finds no file, inspect that
repository's file list and download its Q4_K_M conversion of the exact named
Instruct-2507 model, or use a trusted compatible conversion. Do not substitute
a thinking/base model silently. Review its license/model card and verify the
publisher's file hash before use. Record the runtime release tag, GGUF filename
and SHA-256 with your acceptance results. Runtime release page:
<https://github.com/ggml-org/llama.cpp/releases>.

Do not start a second llama-server manually: the application owns its process.
Port 8081 must be free. The server starts lazily on the first question with
retrieved evidence; it stays loaded until shutdown, cancellation or failure.
Use the model's embedded chat template. If your release lacks required flags,
install a compatible recent CPU build instead of removing privacy/resource flags.

On Linux/macOS, install/build llama.cpp following its upstream instructions
with GPU support disabled, set `MARITIME_LLAMA_SERVER` to the executable and
`MARITIME_MODEL_PATH` to an absolute GGUF path, then use the same Python launcher.
Example shell configuration (substitute paths to installed files):

```sh
export MARITIME_LLAMA_SERVER=/absolute/path/to/llama-server
export MARITIME_MODEL_PATH=/absolute/path/to/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
export MARITIME_INFERENCE_TIMEOUT=180
python scripts/synthetic_preview.py
```

The synthetic launcher overrides operational database settings with ignored
`.preview-synthetic/maritime.db`. For regular local operation, use
`MARITIME_DATA_DIR` with `python scripts/dev.py`; migrations run before startup.
Stop with Ctrl+C before backing up the complete database **and documents directory**.

## Runtime boundaries and configuration

| Setting or limit | Behavior |
| --- | --- |
| `MARITIME_MODEL_PATH` | Absolute/configured local `.gguf`; no download or fallback in the app. |
| `MARITIME_LLAMA_SERVER` | Executable path or `llama-server` on PATH. Never supplied by an upload. |
| `MARITIME_MODEL_PORT` | Loopback model port, default 8081; range 1024–65535. An occupied port is rejected before private prompts are sent. |
| `MARITIME_INFERENCE_TIMEOUT` | 180 seconds by default, including model startup; configurable >0 up to 600. |
| Inference | Context 4096, output at most 512 tokens, one slot/request, temperature 0, GPU layers 0, offline runtime flag, prompt cache RAM disabled. |
| Import | Raw `application/pdf` body, `.pdf` label, PDF signature, at most 10 MiB, 100 pages, 1 million extracted characters. |
| Parser | 30-second subprocess timeout. Linux child address space limited to 768 MiB; Windows does not have an enforced child memory limit here. |
| Retrieval | Per-document FTS5, normalized accents, top three 700-character windows with overlap. No embedding service/vector database. |
| Storage | UUID-named PDFs in `documents/` beside SQLite; filenames are labels, never paths. Source pages/chunks/FTS are in migration 0002; vessel schema unchanged. |

Model status reports **configured**, not a successful model load. A corrupt or
incompatible GGUF produces a runtime error on first use. HTTP inference is only
to the owned loopback process, with environment proxies disabled for that local
connection. Runtime logs are suppressed so prompts/evidence are not logged.
A runtime failure gives a clear error; check executable compatibility and RAM.
The launcher's health endpoint checks database availability, not AI readiness.

Cancel inference sends a cancellation request and aborts the browser connection.
The backend cancels the pending operation and terminates its owned model process,
including startup. A later question reloads the model. Timeout has the same
process-cleanup behavior. Only one inference may run at once; a concurrent
question receives a busy error. There is no persistent job queue.

## Exact acceptance steps on a Windows 16 GB CPU laptop

1. Install/configure runtime and candidate model above. Record CPU, RAM,
   Windows version, runtime tag, GGUF filename/hash. Disconnect Internet after setup.
2. Start `python scripts/synthetic_preview.py`; open <http://127.0.0.1:5173>.
3. In another terminal with the virtual environment active, run:

   ```powershell
   python scripts/create_synthetic_pdf.py synthetic-training.pdf
   ```

4. Import that PDF. It has two pages, both clearly labeled synthetic.
5. Ask **When do lifejacket inspections take place?** Expect an answer stating
   Friday, with page 1 and an exact supporting quote. Expand evidence, inspect
   source page, and compare the original PDF. No actual maritime rule is asserted.
6. Ask **What is the SOLAS regulation number requiring these lifejacket inspections?**
   This shares retrieval keywords but is not answered by the source. Expect an
   insufficient-evidence response, without invented regulation or citations.
7. Ask **Lifejacket inspections diễn ra khi nào? Trả lời bằng tiếng Việt.**
   This retains source keywords while requesting Vietnamese. Also test questions
   matching Vietnamese source text in a Vietnamese PDF with embedded Unicode fonts.
8. Run the actual-model acceptance script while the backend is running:

   ```powershell
   python scripts/validate_local_model.py
   ```

   It imports its own synthetic fixture, requires the real `llama.cpp-local`
   provider, checks Friday/citation integrity, asks an unsupported question with
   overlapping keywords, and confirms Ship Profile was not modified. It exits
   nonzero on failure or missing runtime/model. Review printed results, not only
   the exit status. This is a small acceptance case, not a general accuracy test.
9. Test Cancel during startup/generation, retry, unavailable model (restart with
   a nonexistent path), and timeout (temporarily lower the configured timeout).
10. Create/edit/save/reload Ship Profile; restart the app and confirm saved
    profile and imported PDF pages remain available. Return to AI Workspace.
11. Record cold-start and warm-answer times, peak combined browser/Python/model
    memory, available Windows RAM and paging behavior with Task Manager or
    Resource Monitor. Do not call 16 GB support verified if there is insufficient
    headroom, excessive paging, or unacceptable response time. No performance
    numbers are claimed by this implementation.

## Preview and automated tests

Use `python scripts/synthetic_preview.py` for the isolated synthetic preview,
then open <http://127.0.0.1:5173> **on the computer running it**. A model is needed
for generated answers; importing/inspecting PDFs and existing Ship Profile work
without one. AI Workspace loads independently of vessel-profile availability.

For phone review on the same trusted Wi-Fi, use the existing explicit-origin
launcher, e.g. `python scripts/synthetic_preview.py --host 0.0.0.0 --origin
http://192.168.1.20:5173`, substituting the computer's address. Synthetic data
only; no router forwarding or public deployment. There is no supported cloud
preview URL in this session. See [PREVIEW.md](PREVIEW.md).

With the environment active:

```sh
cd backend
python -m pytest -q
cd ../frontend
npm test
npm run build
```

For Playwright, start the backend on port 8000 against a **disposable migrated
SQLite database** as in README; never use operational data or a retained review
profile. Run `npm run test:e2e` from frontend. On this Linux session, set
`PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium`. Tests generate a synthetic PDF
using the repository `.venv` Python; override `PLAYWRIGHT_PYTHON_EXECUTABLE` if
installed elsewhere. Playwright starts/reuses frontend port 5173.

## Verified results and limitations

See [TASK_02_VALIDATION.md](TASK_02_VALIDATION.md) for fresh test results.

- Source identity/quote validation is mechanical. It cannot prove that a model's
  interpretation logically follows from its quote. Review source evidence.
- Prompt instructions establish a data boundary, not a proof of model immunity
  to prompt injection. The model receives no tools or mutation API; uploaded
  instructions cannot execute code or silently change Ship Profile.
- FTS5 is lexical, not semantic or cross-language search. English/Vietnamese
  questions and answers are supported, but source-language keywords must overlap;
  cross-language paraphrases may return insufficient evidence. No embeddings or
  translation service is silently used. Source tables/maps with poor PDF text
  order and partial scanned pages can yield incomplete evidence. OCR is absent.
- Only one selected document and three short excerpts feed each answer. Long,
  multi-page synthesis may miss relevant passages. Unavailable or insufficient
  evidence must not be treated as evidence that a fact is false.
- Answers are not chat history; previous questions are not persisted or reused.
  No document editing/deletion UI, offline installer, authentication, application
  encryption, immutable audit, or Windows parser memory sandbox is added.
- Local machine access remains trusted. CORS is not authentication; operational
  data must not be exposed over LAN. Imported PDFs are downloaded as attachments;
  PDF viewing/extracted text has no execution tools in the app.
- Real Qwen inference, Vietnamese answer quality, adversarial model behavior,
  disconnected Windows performance and physical phone access remain UNVERIFIED.

No automatic form filling or later task is started. Await approval after Task 02.
