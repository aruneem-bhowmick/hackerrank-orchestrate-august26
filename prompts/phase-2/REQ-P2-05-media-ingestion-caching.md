# REQ-P2-05 — Media Ingestion Caching And Batch Entrypoint

## Traceability
- Source requirement: REQ-P2-05 (SPEC.md §2, Phase 2)
- Depends on: REQ-P2-01, REQ-P2-02, REQ-P2-03, REQ-P2-04 (wraps their
  already-correct, already-hardened `normalize_message` unchanged)
- Unblocks: none within this phase — this is the phase's closing prompt;
  P3 consumes this prompt's `run_media_ingestion` output.

## Objective
`dataset/messages.csv` references several `media_id` values more than once
(`img_008` 3 times, `img_010`/`img_003` 2 times each) — each repeat within
one routing batch would otherwise cost a redundant paid OCR/ASR call. This prompt adds a
media-id-scoped cache wrapping the `OCRClient`/`ASRClient` boundary (not a
change to `normalize_message` itself), and the batch entrypoint,
`run_media_ingestion`, that scores every row of `bundle.messages` and wires
the result into `code/main.py` — the phase's first and only batch-level
production code, mirroring `run_safety_gate`'s role in Phase 1.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the `NormalizedMessage` contract and
  the dataset-grounded media_id-reuse finding from ADR-007/§6.
- REQ-P2-01 through REQ-P2-04 already deliver a fully correct
  `normalize_message(message, bundle, dataset_dir, ocr_client, asr_client)`
  for one message. This prompt does not modify that function's body or
  signature at all — caching is implemented as a decorator around the
  `OCRClient`/`ASRClient` passed in, not as a parameter threaded through
  `normalize_message`, `_normalize_image_message`, or
  `_normalize_voice_message`. This keeps every test written in REQ-P2-01
  through REQ-P2-04 valid unchanged.
- Caching is keyed by the *resolved file path* (a `str(Path)`), not
  `media_id` directly — the two are equivalent for this dataset (one
  `media_id` always resolves to one `file_path` via `lookup_media_file_path`),
  and keying by path avoids adding a `media_id` parameter to `OCRClient`/
  `ASRClient`'s protocol methods, which take only a path today.
- A cached *failure* (a raised `OCRClientError`/`ASRClientError`) is cached
  too, and replayed as a raise on the next call for the same path — a
  media file that fails once (bad key, network blip mid-batch, genuinely
  corrupt file) should not be retried on every one of its repeat
  references within the same batch run.
- `run_media_ingestion` mirrors `run_safety_gate`'s existing shape in
  `code/router/safety/gate.py`: default-construct clients if none are
  passed, process every row of `bundle.messages`, return a
  `dict[message_id, NormalizedMessage]`, and raise if the produced count
  does not match the row count (same "nothing silently dropped"
  discipline REQ-P1-05 established one phase over).

## Files to create or modify
- `code/router/errors.py` — modify: `MediaIngestionError` (already added in
  REQ-P2-01) is reused for the batch-count invariant; no new exception
  class needed.
- `code/router/ingestion/cache.py` — create: `CachingOCRClient`,
  `CachingASRClient`.
- `code/router/ingestion/pipeline.py` — modify: add `run_media_ingestion`.
- `code/main.py` — modify: call `run_media_ingestion` after the existing
  load/validate/safety-gate steps and report a summary line.
- `tests/unit/test_media_ingestion_cache.py` — create.
- `tests/system/test_media_ingestion_batch_system.py` — create.
- `tests/system/test_p2_pipeline_system.py` — create.

## Interfaces & signatures

```python
# code/router/ingestion/cache.py
class CachingOCRClient:
    """Wraps an OCRClient, caching results (and failures) by resolved
    image path so a media_id referenced by multiple messages triggers at
    most one underlying extract() call per run (REQ-P2-05)."""
    def __init__(self, inner: OCRClient) -> None: ...
    def extract(self, image_path: Path) -> OCRResult: ...

class CachingASRClient:
    """As CachingOCRClient, for ASRClient.transcribe."""
    def __init__(self, inner: ASRClient) -> None: ...
    def transcribe(self, audio_path: Path) -> ASRResult: ...
```

```python
# code/router/ingestion/pipeline.py
def run_media_ingestion(
    bundle: DatasetBundle,
    dataset_dir: Path,
    ocr_client: OCRClient | None = None,
    asr_client: ASRClient | None = None,
) -> dict[str, NormalizedMessage]:
    """Normalize every message in bundle.messages; nothing is silently
    dropped. Defaults to build_ocr_client()/build_asr_client() when not
    supplied, each wrapped in the corresponding caching decorator before
    any message is processed, so cache scope is exactly one batch run.
    Raises MediaIngestionError if the produced count does not match
    len(bundle.messages) — a missing entry here would otherwise surface
    only as a mysterious gap much later, in P5's output."""
```

## Implementation details
1. `CachingOCRClient.__init__(self, inner)`: stores `inner` and an empty
   `dict[str, OCRResult | OCRClientError]` cache, private to the instance
   (never shared across `CachingOCRClient` instances — a fresh cache per
   `run_media_ingestion` call, matching "cache scope is exactly one batch
   run").
2. `CachingOCRClient.extract(self, image_path)`:
   - `key = str(image_path)`.
   - If `key` is already cached: if the cached value is an
     `OCRClientError` instance, `raise` it; else `return` it.
   - Else: call `self._inner.extract(image_path)` inside
     `try/except OCRClientError as exc`. On success, cache and return the
     `OCRResult`. On the exception, cache the exception object itself
     (`self._cache[key] = exc`), then re-raise it (`raise`, not `raise exc`,
     to preserve the original traceback).
3. `CachingASRClient` mirrors this exactly for `ASRResult`/`ASRClientError`
   /`transcribe`.
4. `run_media_ingestion`:
   - `ocr_client = CachingOCRClient(ocr_client or build_ocr_client())`.
   - `asr_client = CachingASRClient(asr_client or build_asr_client())`.
   - `normalized = {message["message_id"]: normalize_message(message,
     bundle, dataset_dir, ocr_client, asr_client) for message in
     bundle.messages.to_dict("records")}`.
   - If `len(normalized) != len(bundle.messages)`: raise
     `MediaIngestionError` with a message naming both counts, matching
     `run_safety_gate`'s existing wording pattern exactly (same phrasing
     style, different noun).
   - Return `normalized`.
5. `code/main.py`: after the existing `run_safety_gate(bundle)` call
   (order relative to it does not matter — see `_PREAMBLE.md`), call
   `normalized = run_media_ingestion(bundle, dataset_dir)` (passing the
   same `dataset_dir` already resolved for `load_dataset_bundle`), then
   print a summary: count of image/voice messages processed and count with
   `media_failure=True`, in the same style as the existing
   "Safety gate: N blocked, M borderline, K clean." line. Catch
   `DatasetError` around this call too (or extend the existing `try` block
   to cover it) — `MediaIngestionError` is a `DatasetError` subclass, so
   the existing `except DatasetError` handler in `main()` already covers
   the batch-count-invariant failure mode without new exception-handling
   code, provided the call sits inside (or is moved into) that same `try`
   block. `OCRClientError`/`ASRClientError` never reach `main()` — they are
   fully contained within `normalize_message`/the caching clients per
   REQ-P2-04.

## Standards to apply
- No AI attribution in code comments or docstrings.
- Cache media ingestion results per `media_id`
  (`CachingOCRClient`/`CachingASRClient`), matching the caching discipline
  this requirement names — this is the one prompt in the phase whose whole
  purpose is that cost discipline, so do not skip or stub it.
- `run_media_ingestion` never calls a real network API in a test — every
  test either supplies fakes directly or exercises `CachingOCRClient`/
  `CachingASRClient` wrapping a fake.

## Test suite (exhaustive)
Framework: `pytest`.

- **Unit:** `CachingOCRClient` — two calls with the same `image_path` and a
  `FakeOCRClient` whose `extract` increments a call counter → counter is 1,
  both calls return the identical `OCRResult`; two calls with *different*
  paths → counter is 2; a `FakeOCRClient` that raises `OCRClientError` on
  first call → second call for the same path raises the same exception
  without calling the fake again (counter stays 1). `CachingASRClient`
  mirrors all three cases for `transcribe`/`ASRResult`/`ASRClientError`
  (`test_media_ingestion_cache.py`).
- **Integration:** N/A beyond what the system test below covers — caching
  is a thin decorator with no additional cross-module boundary of its own
  to test in isolation from the batch entrypoint.
- **System:** `run_media_ingestion` run against a loaded `DatasetBundle`
  fixture containing at least one message whose `media_id` repeats (a
  synthetic fixture mirroring the real dataset's `img_008` pattern) and
  `FakeOCRClient`/`FakeASRClient` call counters — confirms the repeated
  `media_id` triggers exactly one underlying call across the whole batch,
  and that the returned dict has exactly one `NormalizedMessage` per
  `message_id` (`test_media_ingestion_batch_system.py`); a second system
  test runs `code/main.py`'s `main()` end to end against the real
  `dataset/` directory with `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` unset
  (via `monkeypatch.delenv`), confirming the whole pipeline still
  completes with exit code 0 and every media message lands in the
  REQ-P2-04 fallback path rather than crashing the run
  (`test_p2_pipeline_system.py`).
- **Acceptance:** "system MUST cache ingestion results by `media_id` so
  repeated media references are not reprocessed" → the call-counter
  assertions in both the unit and system tests are the direct check.
- **Smoke:** `run_media_ingestion` runs against the real `dataset/`
  directory (loaded via `load_dataset_bundle`) with fake clients and
  completes without raising, producing 110 entries.
- **Sanity:** re-running `run_media_ingestion` twice against the same
  bundle and fake clients (two separate calls, two separate caches)
  produces identical output both times — confirms caching does not leak
  state across batch runs or introduce nondeterminism.
- **Regression:** the batch-count invariant (`MediaIngestionError` on a
  count mismatch) — a fixture with a duplicated `message_id` in
  `bundle.messages`, confirming the same guard `run_safety_gate` already
  has one phase over is present here too.
- **End-to-end:** the `test_p2_pipeline_system.py` key-less full run above
  is this phase's local/mocked end-to-end coverage, per `_PREAMBLE.md`'s
  "default to the local/mocked path" guidance; gated live-API e2e (real
  keys, real network, real OCR/ASR accuracy) is intentionally out of the
  automated suite per ADR-007 and should be spot-checked manually once run
  with real keys.
- **API:** N/A — no new external call boundary in this prompt; `cache.py`
  wraps the existing REQ-P2-01/02 client boundaries without adding a new
  one.
- **UI:** N/A — no rendered surface (SPEC.md §3 Non-Goals).

## Acceptance criteria (derived from SPEC.md, made executable)
- "cache ingestion results by `media_id` so repeated media references are
  not reprocessed" → call-counter assertions (unit + system).
- `run_media_ingestion` produces exactly one `NormalizedMessage` per row of
  `bundle.messages`, matching REQ-P0-04/REQ-P5-01's parity discipline →
  the smoke test's `len(normalized) == 110` assertion against the real
  dataset, plus the regression fixture's duplicate-`message_id` guard.
- A key-less run completes end to end without crashing → `test_p2_pipeline_system.py`.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- `run_media_ingestion`'s output matches the `NormalizedMessage` contract
  exactly, one entry per `message_id`.
- `code/main.py` runs `run_media_ingestion` and reports a summary,
  completing successfully against the real `dataset/` directory whether or
  not `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` are set.
- This closes Phase 2: `REQ-P2-01` through `REQ-P2-05`'s own Definitions of
  Done all pass, and the full `tests/unit`, `tests/integration`,
  `tests/system` suite passes together as a final phase-level check.

## Out of scope
- Any P3 evidence-retrieval use of `normalized_text` — this prompt only
  produces the `NormalizedMessage` dict; consuming it for retrieval is
  Phase 3's job.
- Re-running P1's safety gate on `normalized_text` — out of scope for this
  phase entirely; see `_PREAMBLE.md`'s "Role in the pipeline" note on P1/P2
  independence.
