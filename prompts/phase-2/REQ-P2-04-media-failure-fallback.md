# REQ-P2-04 — Media Failure Fallback Contract

## Traceability
- Source requirement: REQ-P2-04 (SPEC.md §2, Phase 2)
- Depends on: REQ-P2-01, REQ-P2-02, REQ-P2-03 (the fallback behavior this
  prompt locks down is already implemented across those three — this
  prompt is the exhaustive test/regression lock plus any gap-fix, not new
  feature logic, mirroring how REQ-P1-06 closed out Phase 1's borderline
  contract over already-implemented signal scoring)
- Unblocks: REQ-P2-05

## Objective
REQ-P2-01/02 already built `_fallback_normalized_message`, the
`OCRClientError`/`ASRClientError` catch sites, and the "OCR/ASR reported
failure" branches — because it is not possible to correctly implement
"the resulting text (if any) feeds `normalized_text`" without also deciding
what happens when there is no resulting text. This prompt is where that
already-built behavior is audited against every failure mode REQ-P2-04
names explicitly (blank output, garbled output, silent audio, unclear
audio, and — found by inspecting the actual implementation, not named
verbatim in the requirement text but structurally the same class of bug —
a missing media record, a missing API key, and a raised client exception),
locked in with a regression fixture set, and any gap the audit finds is
fixed here rather than left for a later prompt to discover by accident.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the `NormalizedMessage` contract and
  the REQ-P2-04 requirement text verbatim: "OCR/ASR failure (blank/garbled
  output, silent or unclear audio) MUST set `media_failure: true` and route
  with a lowered confidence and an explicit fallback reason — never crash,
  never silently guess as if ingestion succeeded."
- "Lowered confidence" is REQ-P2-01's `_FAILURE_CONFIDENCE_CAP = 0.2`
  module constant (defined in `pipeline.py`, reused by REQ-P2-02's voice
  path) — audit that every failure path actually applies it, not just the
  ones this prompt happens to test first.
- "Explicit fallback reason" is `NormalizedMessage.media_failure_reason`
  (the ADR-007 contract extension) — audit that it is always a non-empty,
  specific string whenever `media_failure` is `True`, and always `None`
  when it is `False`. A generic "ingestion failed" string with no
  cause-specific detail is a gap to fix, not a passing case — mirrors
  REQ-P1-05's "non-generic risk_signals" bar one phase over.
- This prompt does not add a new external call, a new module, or change
  any function's return type — only tests, a small fixture set, and any
  bug fix the audit surfaces (which may touch `pipeline.py`, `ocr.py`, or
  `asr.py`'s existing bodies).

## Files to create or modify
- `code/router/ingestion/pipeline.py` — modify only if the audit in
  Implementation Details finds a real gap; otherwise docstring
  clarification only (state the fallback contract explicitly on
  `normalize_message`, the way `code/router/safety/gate.py`'s module
  docstring states the override contract for P1).
- `code/router/ingestion/ocr.py` / `code/router/ingestion/asr.py` — modify
  only if the audit finds a real gap in confidence clamping or reason
  wording.
- `tests/fixtures/ingestion_media_failures.py` — create: a table of
  synthetic failure-mode fixtures (one entry per named failure mode below)
  used by both the unit and integration suites, mirroring
  `tests/fixtures/safety_scam_messages.py`'s role in Phase 1.
- `tests/unit/test_media_failure_fallback.py` — create.
- `tests/integration/test_media_failure_fallback_integration.py` — create.

## Interfaces & signatures
No new public interface. This prompt exercises the existing
`normalize_message`, `_normalize_image_message`, `_normalize_voice_message`,
`OCRClient.extract`, and `ASRClient.transcribe` surfaces built in
REQ-P2-01/02/03 against every failure mode below, asserting the exact
`NormalizedMessage` shape each produces:

```text
media_failure == True
media_confidence <= 0.2   # _FAILURE_CONFIDENCE_CAP
media_failure_reason is not None and media_failure_reason.strip() != ""
normalized_text == <caption for images, "" for voice, per ADR-007>
```

## Implementation details
1. Enumerate every failure mode this prompt must cover, and for each,
   write a fixture (message dict + fake client behavior) plus a test
   asserting the four invariants above:
   - **Blank OCR output**: `FakeOCRClient` returns `OCRResult(text="",
     confidence=0.4, category="screenshot", failure=True,
     failure_reason="...")`.
   - **Garbled/low-confidence OCR output**: `FakeOCRClient` returns
     `OCRResult(text="●●●unreadable●●●", confidence=0.05, category=None,
     failure=True, failure_reason="...")` — text present but the client
     itself flagged failure; confirm the pipeline trusts the client's
     `failure` flag over the mere presence of a non-empty string.
   - **OCR client exception**: `FakeOCRClient.extract` raises
     `OCRClientError("simulated network failure")`.
   - **Silent audio**: `FakeASRClient` returns `ASRResult(text="",
     confidence=0.0, failure=True, failure_reason="no speech segments
     detected in the audio")`.
   - **Unclear audio**: `FakeASRClient` returns `ASRResult(text="mostly
     noise", confidence=0.1, failure=True, failure_reason="silent or
     unclear audio: no reliable speech detected")`.
   - **ASR client exception**: `FakeASRClient.transcribe` raises
     `ASRClientError("simulated timeout")`.
   - **Missing API key**: `build_ocr_client()`/`build_asr_client()` with
     the relevant env var unset, then their returned client's
     `extract`/`transcribe` called directly — confirm the raised
     `OCRClientError`/`ASRClientError` message names the missing variable
     specifically (not a generic "something went wrong"). Pass each same
     client through `normalize_message` with a matching media row and
     assert `media_failure=True`, `media_confidence <= 0.2`, a non-empty
     failure reason, and caption-only image text or an empty voice
     transcript.
   - **Missing media record**: an image/voice message whose `media_id`
     has no row in `bundle.images`/`bundle.voice_notes`.
   - **Blank media_id**: an image/voice message with `media_id == ""`.
2. For each fixture, assert all four invariants from "Interfaces &
   signatures" above, plus the mode-specific detail: the image fixtures'
   `normalized_text` equals the message's caption exactly (not empty, not
   the garbled OCR text); the voice fixtures' `normalized_text` equals
   `""` exactly.
3. If any fixture's assertions fail against the current implementation,
   that is a real gap — fix it in `pipeline.py`/`ocr.py`/`asr.py` (common
   candidates: a missing `.strip()` before an emptiness check, a
   `min(confidence, cap)` applied on one path but not another, a
   `failure_reason` left `None` on the client-exception path). Do not
   change the fallback *design* (the branches and constants set up in
   REQ-P2-01/02/03) — only fix a genuine mismatch between that design and
   its implementation.
4. Add the module docstring/inline clarification on `normalize_message`
   once the audit is clean: state the fallback contract explicitly, the
   way `code/router/safety/gate.py`'s module docstring states P1's
   override contract, so a future change to this function has the
   invariant written down next to the code it constrains.

## Standards to apply
- No AI attribution in code comments or docstrings.
- Every fixture in `tests/fixtures/ingestion_media_failures.py` is tagged
  with a short name identifying its failure mode (e.g.
  `BLANK_OCR_OUTPUT`, `SILENT_AUDIO`) so a failing test's fixture name
  alone identifies which REQ-P2-04 scenario broke.

## Test suite (exhaustive)
Framework: `pytest`. All failure modes are exercised via fakes; no real
network or filesystem edge case (e.g. actually corrupting a JPEG) is
needed since the failure is injected at the client boundary, matching
REQ-P2-01/02's own test approach.

- **Unit:** one test per failure mode listed in Implementation Details,
  each asserting the four shared invariants plus its mode-specific detail
  (`test_media_failure_fallback.py`).
- **Integration:** the same failure modes run through `normalize_message`
  against a loaded `DatasetBundle` fixture (not just the private
  `_normalize_*` helpers), confirming the fallback contract holds at the
  public entrypoint boundary too
  (`test_media_failure_fallback_integration.py`).
- **System:** N/A for this prompt — REQ-P2-05's batch/system test confirms
  no failure mode crashes a full-bundle run.
- **Acceptance:** "MUST set `media_failure: true` and route with a lowered
  confidence and an explicit fallback reason — never crash, never silently
  guess as if ingestion succeeded" → each of the nine fixtures above is a
  direct pass/fail check of exactly this sentence.
- **Smoke:** each failure-mode fixture runs through `normalize_message`
  without raising an unhandled exception (the "never crash" half of the
  requirement, checked structurally by the test simply not needing a
  `pytest.raises` block for any of them except the two explicitly-checked
  "missing API key" cases, which raise from the *client* by design, not
  from `normalize_message`).
- **Sanity:** re-running the full fixture table after this prompt's
  docstring-only (or gap-fix) change still produces identical
  `NormalizedMessage` values — a narrow before/after diff check.
- **Regression:** `tests/fixtures/ingestion_media_failures.py` itself is
  the regression fixture set for this contract going forward; any later
  phase touching `pipeline.py` re-runs it unchanged.
- **End-to-end:** N/A — see REQ-P2-01's identical justification.
- **API:** N/A — no new external call boundary; the client-exception and
  missing-key fixtures reuse REQ-P2-01/02's existing API-boundary tests'
  fakes rather than re-testing request/response shaping here.
- **UI:** N/A — no rendered surface (SPEC.md §3 Non-Goals); `media_failure_reason`
  is internal signal for later phases (eventually P5's `reason` string),
  not itself a rendered surface.

## Acceptance criteria (derived from SPEC.md, made executable)
- "blank/garbled output ... MUST set `media_failure: true`" → blank-OCR and
  garbled-OCR fixtures.
- "silent or unclear audio ... MUST set `media_failure: true`" →
  silent-audio and unclear-audio fixtures.
- "route with a lowered confidence" → every fixture's
  `media_confidence <= 0.2` assertion.
- "an explicit fallback reason" → every fixture's non-empty,
  mode-specific `media_failure_reason` assertion.
- "never crash" → every fixture (except the two by-design client-level
  raises) completes without an unhandled exception.
- "never silently guess as if ingestion succeeded" → every fixture's
  `media_failure == True` assertion, paired with the caption-only /
  empty-string `normalized_text` assertion (never the garbled/failed
  client text).

## Definition of Done
- All nine failure-mode fixtures pass all four shared invariants plus
  their mode-specific assertion.
- All applicable test types implemented (others marked N/A with reason).
- Any gap found during the audit is fixed, documented in this prompt's
  commit, and covered by the fixture that caught it.
- No change to the `NormalizedMessage` contract or any public function
  signature in this prompt — only behavior-matching fixes and docstrings.

## Out of scope
- Any caching layer (REQ-P2-05) — this prompt's fixtures call the fake
  clients directly/via `normalize_message`, uncached, once per test.
- Wiring a batch entrypoint into `code/main.py` (REQ-P2-05).
