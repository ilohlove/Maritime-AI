# Hybrid retrieval V1

Baseline: `feature/extraction-foundation`, `b0bac6d`. Branch:
`feature/hybrid-retrieval-v1`. PDF remains the only import format. The local LLM
provider, source extraction/identity contracts and AI Workspace layout are unchanged.
No cloud AI, OCR, separate vector database or additional model framework is added.

**Real multilingual semantic quality: UNVERIFIED.** The official GGUF download
host returned proxy HTTP 403. No embedding weights were downloaded or executed.
Deterministic vectors in unit tests prove plumbing, not Vietnamese/English quality.

## Candidate evaluation

Initial candidate: `Qwen/Qwen3-Embedding-0.6B` (upstream), proposed GGUF conversion
`Qwen/Qwen3-Embedding-0.6B-GGUF`, **Q8_0**. The upstream README documents 0.6B,
1024-dimensional embeddings, multilingual retrieval, last-token pooling and
instruction-conditioned queries. Those are publisher statements, not measurements
from this application. Source inspected:
<https://github.com/QwenLM/Qwen3-Embedding>.

Attempted weight URL:
`https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/main/Qwen3-Embedding-0.6B-Q8_0.gguf`.
The proxy rejected the destination with HTTP 403, so the current GGUF file list,
license for that exact artifact, hash and runtime compatibility remain unverified.
Do not bypass access restrictions, use unknown mirrors, or download automatically.
A trusted compatible GGUF may be configured after its upstream/license/hash are checked.

## Provider and offline boundary

The small `EmbeddingProvider` exposes `identity`, asynchronous `embed(texts,
purpose)` and `close`. `LocalEmbeddingProvider` owns a separate llama-server at
loopback port 8082, with an explicitly configured local GGUF. It does not share or
modify the answer-generation provider or accept an external inference URL.

Runtime configuration: CPU-only (`--n-gpu-layers 0`), `--embedding`, last pooling,
4096 context, 2048 batch/ubatch, one slot, two generation threads, offline mode,
no web UI, prompt-cache RAM disabled. The llama.cpp binary obtained during the
preceding validation (build 11960) advertises the required embedding/pooling flags;
loading the actual embedding GGUF has NOT been tested. An occupied port is refused
before private input is sent. Loopback HTTP ignores inherited outbound proxies;
normal network/TLS configuration is otherwise preserved.

Queries receive this versioned instruction prefix; document text is not prefixed:

```text
Instruct: Given a maritime question, retrieve relevant passages that answer the question
Query: <original Vietnamese or English question>
```

Vectors must be finite, nonzero and have consistent dimensions. They are L2
normalized, stored as little-endian float32, and searched using cosine similarity.
The model identity hashes weight content, runtime executable and pooling/query
recipe. Changed weight file metadata requires an app restart; a new identity
never reads another model's vectors. Treat runtime binaries/libraries as an
immutable installation and revalidate/reindex after replacing them.

No private document, prompt, vessel information or vector is sent outside the
local machine. Embeddings can contain sensitive derived information: protect and
back up SQLite together with original documents. This adds no application encryption.

## Persistence and incremental indexing

Migration `0004_embeddings` adds only `chunk_embeddings`, keyed by
`(chunk_id, model_id)`, with source-text hash, dimensions and vector bytes.
Foreign keys reference existing chunks. Original PDFs, FTS5, text, document IDs,
revision IDs, unit IDs and locators remain untouched. Downgrade removes derived
vectors only; original source data remains.

After successful PDF storage, the API attempts indexing in batches of eight.
Only missing/stale vectors for the selected model are embedded; an unchanged
index is reused after restart. Each successful batch commits atomically. Failure
or a deadline can leave a partial derived index; subsequent indexing resumes
without re-embedding completed unchanged batches. Changed chunk hashes are
recomputed. Old model spaces are retained, not mixed; automatic vector garbage
collection is outside V1.

A failed/cancelled embedding operation does not delete the already committed
PDF. A per-service lock serializes indexing/query embedding. Waiting callers can
cancel/time out without terminating another caller's owned runtime. Cancellation
of an active operation and application shutdown close the owned embedding process.
Use one backend worker; no distributed job queue is introduced.

Endpoints (no UI redesign):

- `GET /api/retrieval/status`: last retrieval/index outcome; `not_checked` before use.
- `POST /api/documents/{document_id}/index`, JSON `{}`: retry/backfill indexing,
  including PDFs imported before migration 0004. Origin/JSON write checks apply.
- Import responses add `semantic_index`. Question responses add `retrieval` and
  a fallback notice when only FTS5 could be used. The existing notice area displays it.

First search also fills missing embeddings for the selected document, so older
sources do not require reimport. An import or search has a bounded embedding
budget (60 seconds by default, including load/index time and lock wait). Large
sources can require explicit retries to complete. Concurrent document imports
can commit sources while their derived indexing waits or falls back.

## Fusion and evidence integrity

Existing FTS5 normalization/tokenization/BM25 is preserved. Its helper defaults
to the original top three; hybrid requests up to 20 lexical candidates. Semantic
search scans vectors **only for the selected document and current model**, keeping
up to 20 candidates above a configurable cosine floor. Python scanning avoids a
vector database for the small, single-document corpus (up to roughly 2,000 chunks
at current extraction limits). Its scale/latency must be measured before expanding.

Fuse by equal-weight reciprocal rank fusion:

`RRF(chunk) = sum(1 / (60 + rank_in_list))`

Deduplicate by existing evidence/chunk ID, take the top three. Ties favor lexical
rank, then numeric chunk ID. Raw BM25 and cosine magnitudes are not added together.
The cosine floor defaults to **0.5 as an uncalibrated starting value**, not a
validated answerability threshold. It must be calibrated with real weights on
held-out examples; lowering it can increase unsupported candidates.

Missing model, malformed vectors, inference failure or incomplete indexing returns
the original FTS5 top-three results with a semantic-unavailable notice. The
benchmark refuses to label this fallback as a measured hybrid result. Query/model
timeout/cancellation closes active inference; source data and FTS remain usable.

Fused evidence is constructed from the existing source joins, not generated by
the embedding model. Every item retains exact document/revision/unit IDs, locator
and original excerpt. The unchanged quote/ID checks validate the answer provider's
citations against this evidence. Retrieval is not an answerability classifier:
unsupported questions may retrieve keyword-similar passages. The existing LLM must
still decline unsupported claims. Real LLM refusal/grounding remains unverified.

## Setup and reproduction

Install the existing backend/frontend dependencies as in README. No new Python or
npm dependency is required. Obtain a recent CPU llama.cpp runtime and the candidate
GGUF manually from a trusted source. Check license and publisher hash first.
Example download on a machine where the host is permitted (manifest must be checked):

```sh
hf download Qwen/Qwen3-Embedding-0.6B-GGUF --include '*Q8_0.gguf' --local-dir models/embeddings
```

`hf` is an optional setup CLI, not a runtime dependency. Set in the terminal that
starts the backend (PowerShell uses `$env:NAME = 'value'`):

```sh
export MARITIME_LLAMA_SERVER=/absolute/path/to/llama-server
export MARITIME_EMBEDDING_MODEL_PATH=/absolute/path/to/Qwen3-Embedding-0.6B-Q8_0.gguf
export MARITIME_EMBEDDING_PORT=8082
export MARITIME_EMBEDDING_TIMEOUT=60
export MARITIME_SEMANTIC_MIN_SCORE=0.5
python scripts/synthetic_preview.py
```

The answer model remains configured separately with `MARITIME_MODEL_PATH` and
port 8081. Retrieval benchmarking does not require answer-model weights. If no
embedding model is configured, the app intentionally uses FTS5. Do not start an
embedding llama-server manually: the application owns it. All ports remain loopback
unless the existing synthetic preview is explicitly configured for phone review.

Benchmark from the repository root with its virtual environment active:

```sh
python scripts/benchmark_retrieval.py --mode fts5 --output fts5-results.json
python scripts/benchmark_retrieval.py --mode hybrid --output hybrid-results.json
```

The harness creates an actual six-page synthetic PDF, extracts/imports it into a
new temporary migrated SQLite database, runs the existing production retrieval
service and removes only that disposable directory. It never injects mock
embeddings. Hybrid mode requires real configured weights and every query to stay
in hybrid mode; otherwise metrics are null and status is UNVERIFIED. Record the
model file/hash, runtime version, settings, CPU/OS and results for each real run.

## Benchmark methodology and actual results

Dataset: `benchmarks/hybrid_retrieval_v1.json`, six English synthetic passages,
10 supported queries (3 English, 4 Vietnamese, 1 exact reference, 2 equipment-ID
queries), plus 3 unsupported controls. Regulatory labels are fictional test
references, not assertions of maritime requirements. Each relevant page is one
unit/chunk in this corpus. No tuning on a held-out set has been performed.

Recall@3 = fraction of expected relevant units found among the first three.
MRR@3 = reciprocal first relevant rank, zero if absent in those three. Average
only supported queries; unsupported queries have no relevant target, so they
are reported separately as candidate rate, not counted as successful answers.
All returned source IDs/locators/excerpts are checked against stored units.

Actual Linux **FTS5-only** baseline (one measured pass):

| Group | Count | Recall@3 | MRR@3 |
| --- | ---: | ---: | ---: |
| All supported | 10 | 0.60 | 0.60 |
| English | 3 | 1.00 | 1.00 |
| Vietnamese without English terms | 4 | 0.00 | 0.00 |
| Exact reference | 1 | 1.00 | 1.00 |
| Equipment IDs | 2 | 1.00 | 1.00 |

Unsupported candidate rate: 1/3. This includes an overlapping-keyword question;
it is evidence of the need for answer refusal, not a claim that retrieval failed
its task. Source integrity checks passed for returned excerpts.

FTS query latency mean **0.160 ms**, nearest-rank p95 **0.481 ms** on this tiny
local corpus. This times retrieval only, excluding import/process startup.
Python lifetime peak RSS **67,842,048 bytes**; largest finished child peak RSS
**66,924,544 bytes** (includes PDF parsing, not embedding inference). These are
separate high-water marks, not summed/concurrent memory, Windows performance,
or semantic-model measurements. One small pass does not establish production SLOs.

Raw files: `benchmarks/results/fts5-baseline.json` and
`benchmarks/results/hybrid-unverified.json`. **Real hybrid Recall/MRR, embedding
latency/RAM and Vietnamese semantic quality are UNVERIFIED** because the model
host was denied. No mock-derived quality metric is reported.

For real performance acceptance, repeat cold and warm runs on Windows 16 GB CPU
hardware, sample model/Python/browser working sets and available RAM/paging,
report index time separately from query time, and compare held-out bilingual
questions with FTS5 under identical corpus/settings. Linux `resource` output
in the harness is lifetime process/finished-child RSS, not per-query model peak;
on Windows it explicitly reports memory unmeasured. Use Task Manager/Resource
Monitor or a validation-only process sampler; do not infer Windows memory from Linux.

## Tests and remaining gates

Deterministic vectors test persistence/restart reuse, changed model/content,
incremental batches and interruption/resume, scope, threshold filtering, RRF,
invalid vectors, missing model, timeouts, cancellation and citation source IDs.
They do NOT prove multilingual quality. Existing PDF/Ship Profile and source
validation tests remain required; browser answer fixtures remain labeled stubs.

Remaining: real GGUF load/API conformance; Recall/MRR gain on Vietnamese and held-out
maritime terms; calibration of similarity floor; index/query latency and model
working set; unsupported-answer refusal using a real LLM; Windows 16 GB and physical
phone acceptance. No new formats, OCR, cloud provider, reranker, UI redesign or
main merge is authorized by this implementation.

## Execution summary

On this Linux Codex environment: **76 backend tests, 17 frontend tests and all
3 existing Chromium browser tests passed; TypeScript/production build passed**.
The backend suite includes the existing PDF, extraction-migration, identity,
quote-validation and Ship Profile checks. One upstream Starlette/httpx TestClient
deprecation warning remains. Browser tests used disposable SQLite at
`/tmp/hybrid-browser-data/test.db` with frontend 5178/backend 8005 and no embedding
weights, verifying the FTS5 fallback path. The successful answer-display browser
fixture is explicitly labeled a stub, not real inference.

No frontend source, LLM provider, dependency declaration or source-extraction
contract was changed. Real GGUF semantic benchmarking, multilingual answer quality,
Windows/physical Android and remote CI were not executed. No public deployment
or merge into main was performed.
