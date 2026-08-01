# Phase 2 — Multimodal Ingestion — Index

## Objective (SPEC.md §2, Phase 2)

Normalize every message — text, image, or voice — to text before it reaches
personalization/retrieval, per `SPEC.md` §0's pipeline: OCR/ASR normalization
sits between the user-independent safety gate and P3's text-similarity
retrieval, so both can operate on one uniform `normalized_text` field
regardless of a message's original modality.

## Definition of Done for the phase

- Every `REQ-P2-01` through `REQ-P2-05` requirement's own Definition of Done
  has passed.
- The phase's output contract (`SPEC.md` §1.2, `NormalizedMessage`, as
  amended by ADR-007) holds against a real batch: `run_media_ingestion` run
  against the actual `dataset/` (via `code/main.py`) completes without
  error and produces one normalized message per row of
  `dataset/messages.csv` — 110 entries.
- Every named failure mode in REQ-P2-04 (blank/garbled OCR, silent/unclear
  audio, a raised client exception, a missing API key, a missing media
  record) sets `media_failure=true` with a lowered confidence and a
  specific reason, never crashes, and never fabricates text.
- A `media_id` referenced by more than one message (e.g. the real
  dataset's `img_008`, referenced 4 times) triggers its underlying
  OCR/ASR call exactly once per batch run.
- `code/router/ingestion/`'s public functions and dataclasses are fully
  docstringed.

## How to execute

1. Read `_PREAMBLE.md` in full.
2. Execute the prompts below in the listed order. Each prompt's own Files
   to create/modify, Interfaces & signatures, and Test suite sections are
   self-contained given the preamble — no need to re-read `SPEC.md` unless
   a prompt says otherwise.
3. Run that prompt's full test suite before moving to the next; do not
   start a later prompt with an earlier one's tests failing.
4. After REQ-P2-05 (the last prompt) passes, run the entire
   `tests/unit`, `tests/integration`, `tests/system` suite together once
   more as a final phase-level check.

## Prompts, in execution order

| # | Prompt | Summary |
|---|---|---|
| 1 | `REQ-P2-01-image-ocr-extraction.md` | `NormalizedMessage` contract, media-file lookup helpers, `OCRClient`/`AnthropicOCRClient`, and `normalize_message`'s text/image branches. Voice raises `NotImplementedError` until prompt 2. |
| 2 | `REQ-P2-02-voice-asr-transcription.md` | `ASRClient`/`OpenAIWhisperASRClient`, and `normalize_message`'s real voice branch — same downstream shape as text/image, no forked logic. |
| 3 | `REQ-P2-03-image-category-classification.md` | Centralizes the image/voice taxonomy in `categories.py` and wires the OCR call's already-returned `category` field into `media_category` — no new API call. |
| 4 | `REQ-P2-04-media-failure-fallback.md` | Exhaustive audit and regression lock of the fallback contract already built across prompts 1–3: every named failure mode sets `media_failure`, a lowered confidence, and a specific reason, never crashes. |
| 5 | `REQ-P2-05-media-ingestion-caching.md` | `CachingOCRClient`/`CachingASRClient` (media-id-scoped, via resolved path) and `run_media_ingestion`, the batch entrypoint, wired into `code/main.py`. Closes out the phase. |

See `traceability.md` for the full requirement → prompt → test-file matrix.
