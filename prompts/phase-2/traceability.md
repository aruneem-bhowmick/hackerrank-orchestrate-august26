# Phase 2 — Requirement → Prompt → Test File Traceability

| Requirement | Prompt | Production files | Test files |
|---|---|---|---|
| REQ-P2-01 | `REQ-P2-01-image-ocr-extraction.md` | `code/router/errors.py`, `code/router/ingestion/__init__.py`, `code/router/ingestion/message.py`, `code/router/ingestion/media.py`, `code/router/ingestion/ocr.py`, `code/router/ingestion/pipeline.py` | `tests/unit/test_normalized_message_contract.py`, `tests/unit/test_media_lookup.py`, `tests/unit/test_ocr_client.py`, `tests/unit/test_normalize_image_message.py`, `tests/integration/test_ocr_pipeline_integration.py`, `tests/fixtures/ingestion_images/` |
| REQ-P2-02 | `REQ-P2-02-voice-asr-transcription.md` | `code/router/errors.py`, `code/router/ingestion/asr.py`, `code/router/ingestion/pipeline.py` | `tests/unit/test_asr_client.py`, `tests/unit/test_normalize_voice_message.py`, `tests/integration/test_asr_pipeline_integration.py`, `tests/fixtures/ingestion_audio/` |
| REQ-P2-03 | `REQ-P2-03-image-category-classification.md` | `code/router/ingestion/categories.py`, `code/router/ingestion/ocr.py`, `code/router/ingestion/pipeline.py` | `tests/unit/test_image_category_classification.py` |
| REQ-P2-04 | `REQ-P2-04-media-failure-fallback.md` | `code/router/ingestion/pipeline.py` (docstring; fix only if a gap is found) | `tests/unit/test_media_failure_fallback.py`, `tests/integration/test_media_failure_fallback_integration.py`, `tests/fixtures/ingestion_media_failures.py` |
| REQ-P2-05 | `REQ-P2-05-media-ingestion-caching.md` | `code/router/ingestion/cache.py`, `code/router/ingestion/pipeline.py`, `code/main.py` | `tests/unit/test_media_ingestion_cache.py`, `tests/system/test_media_ingestion_batch_system.py`, `tests/system/test_p2_pipeline_system.py` |

## Requirement → SPEC.md §4 test-taxonomy row cross-reference

`SPEC.md` §4 pins two Phase-2 rows explicitly; both are satisfied here:

- "REQ-P2-04 | Unit | Feed corrupted/blank media path → graceful fallback,
  no crash" → satisfied by every failure-mode fixture in
  `test_media_failure_fallback.py`.
- "REQ-P2-05 | Unit | Same media_id referenced by two messages →
  underlying OCR/ASR client invoked exactly once" → satisfied by
  `test_media_ingestion_cache.py`'s call-counter assertions and
  `test_media_ingestion_batch_system.py`'s batch-level confirmation
  against a synthetic repeated-`media_id` fixture.

## Test-type coverage summary

Every prompt's Test suite section populates all ten taxonomy types (Unit,
Integration, System, Acceptance, Smoke, Sanity, Regression, End-to-end,
API, UI), marking N/A with an explicit reason where a type does not apply.
Notable N/A patterns across this phase:

- **API**: populated for REQ-P2-01/REQ-P2-02 (the Anthropic vision and
  Whisper request/response shaping) and REQ-P2-03 (the tool schema's
  category enum, folded into REQ-P2-01's existing API-boundary test file
  rather than duplicated); N/A for REQ-P2-04 (reuses those existing
  boundary tests, adds no new external call) and REQ-P2-05 (a caching
  decorator around an existing boundary, not a new one).
- **UI**: N/A for every REQ-P2-* prompt — no rendered surface exists until
  P5's `output.csv`; `normalized_text`/`media_category`/
  `media_failure_reason` are internal signal for P3/P4/P5, not read
  directly by a person at this stage.
- **System**: concentrated in REQ-P2-05 (the batch entrypoint and
  `code/main.py` wiring, including a key-less full run against the real
  `dataset/` directory), rather than duplicated across every prompt —
  mirrors Phase 1's REQ-P1-05 pattern.
- **End-to-end**: every prompt defaults to the local/mocked path per
  `_PREAMBLE.md`; REQ-P2-05's key-less full-dataset run is this phase's
  end-to-end coverage. Gated live-API e2e (real `ANTHROPIC_API_KEY`/
  `OPENAI_API_KEY`, real network, real OCR/ASR output quality) is
  intentionally out of the automated suite per ADR-007 and should be
  spot-checked manually once run with real keys — this is a real
  limitation, not silently dropped coverage; see ADR-007 in `SPEC.md` §5
  for the explicit statement of that boundary.
