# Phase 2 — Multimodal Ingestion — Shared Preamble

If anything below seems incomplete or you need more context than this
extract provides, read `SPEC.md` in full before proceeding — this preamble
is a convenience extract, not a replacement for it.

## Role in the pipeline

Per `SPEC.md` §0, the router is two coupled decisions: a user-independent
safety gate, then a personalized value/urgency score. This phase sits
between them, normalizing every message — regardless of original modality —
to text so both the safety gate's text-pattern detectors and P3's
text-similarity retrieval can operate uniformly.

```text
P0 Data Load/Validate
  → P1 Safety Gate (user-independent)
    → P2 Multimodal Ingestion (OCR/ASR normalization to text)   <-- this phase
      → P3 Personalization & Evidence Retrieval
        → P4 Decision Fusion & Confidence Calibration
          → P5 Output Generation & Validation
```

P2 consumes the `DatasetBundle` produced by P0
(`code/router/dataset/loader.py`, already implemented and merged) — in
particular `bundle.messages`, `bundle.images`, and `bundle.voice_notes` —
and, per row of `bundle.messages`, produces a `NormalizedMessage` (§1.2).
P2 does **not** consume `UserTimeline`, `users`, `group_members`,
`business_accounts`, or `user_business_history` — normalization is about
turning media into text, not about the receiving user, mirroring P1's own
user-independence discipline one layer up. P2 also does **not** re-run or
duplicate P1's safety scoring; `run_safety_gate` (already implemented) scores
`message_text` as loaded, and P2's `normalized_text` is what P3/P4 consume
downstream, not a re-input to P1. Ordering between P1 and P2 in `code/main.py`
is not itself a correctness requirement either direction can run — but do
not make P1 depend on P2's output, since REQ-P1-01 requires P1's verdict be
independent of anything besides the raw message and business data it
already reads.

## Requirements in this phase (SPEC.md §2, Phase 2 — verbatim)

- **REQ-P2-01**: Every `media_type: image` message MUST be run through OCR
  before routing; the resulting text (if any) feeds `normalized_text`.
- **REQ-P2-02**: Every `media_type: voice` message MUST be run through ASR;
  the resulting transcript feeds `normalized_text` and is then processed by
  the *same* downstream text pipeline as native text — no forked logic.
- **REQ-P2-03**: Image messages MUST be classified into a coarse
  `media_category` (e.g. poster/promo, screenshot, document photo, meme,
  personal photo) to inform `message_type` in P4.
- **REQ-P2-04**: OCR/ASR failure (blank/garbled output, silent or unclear
  audio) MUST set `media_failure: true` and route with a lowered confidence
  and an explicit fallback reason — never crash, never silently guess as if
  ingestion succeeded.
- **REQ-P2-05**: Media ingestion cost is real (API calls / inference time);
  system MUST cache ingestion results by `media_id` so repeated media
  references are not reprocessed.

## Data contracts (SPEC.md §1 — quoted verbatim)

### Input this phase reads (§1.0, §1.1)

```text
DatasetBundle = {
  messages: DataFrame,                 # dataset/messages.csv (read-only)
  users: DataFrame,
  groups: DataFrame,
  group_members: DataFrame,
  business_accounts: DataFrame,
  user_business_history: DataFrame,
  message_history: DataFrame,
  message_events: DataFrame,
  images: DataFrame,
  voice_notes: DataFrame,
  daily_notification_summary: DataFrame,
  sample_messages: DataFrame,          # calibration only, per REQ-P5-02
  output_template: DataFrame,          # dataset/output.csv, shape reference
                                        # only, for REQ-P0-04 / REQ-P5-01
}
```

`messages.csv` row fields (from `problem_statement.md` §Input schema,
mirrored in `code/router/dataset/schema.py`'s `DATASET_FILES` registry):
`message_id, user_id, conversation_type, group_id, business_id,
sender_user_id, created_at, message_text, media_type, media_id,
forwarded_count`. `media_type` is `""`, `"image"`, or `"voice"`.

`images.csv` row fields: `image_id, file_path` — `file_path` is relative to
`dataset/` (e.g. `media/images/img_001.jpg`).

`voice_notes.csv` row fields: `voice_note_id, file_path` — `file_path` is
relative to `dataset/` (e.g. `media/audio/vn_001.mp3`).

### Output this phase produces (§1.2, verbatim, as amended by ADR-007)

```text
{
  message_id, user_id, conversation_type, group_id, business_id,
  sender_user_id, created_at, media_type,
  normalized_text: str,       # message_text OR OCR/ASR transcript
  media_confidence: float,    # 1.0 for native text; OCR/ASR conf otherwise
  media_failure: bool,        # true if OCR/ASR could not produce usable text
  media_category: str | null, # e.g. poster, screenshot, doc-photo, voice-note
  media_failure_reason: str | null  # human-readable cause when media_failure
                                     # is true; null otherwise
}
```

This is the `NormalizedMessage` contract. Field names and types are exact —
no renames, no extra required fields beyond `media_failure_reason` (already
authorized by ADR-007; do not add further fields without a new SPEC.md edit
first). For a text message (`media_type == ""`), `normalized_text ==
message_text`, `media_confidence == 1.0`, `media_failure == False`,
`media_category is None`, `media_failure_reason is None` — P2 still produces
a `NormalizedMessage` for every row of `bundle.messages`, not just media
rows, matching REQ-P0-04/REQ-P5-01's one-row-per-message-id discipline one
layer up.

## Resolved ADRs binding this phase (SPEC.md §5 — verbatim)

> **ADR-001** (2026-08-01): OCR engine choice — Anthropic's vision-capable
> Messages API. See ADR-007 for the full rationale and implementation notes.
>
> **ADR-002** (2026-08-01): ASR engine choice — OpenAI's Whisper
> transcription API. See ADR-007 for the full rationale and implementation
> notes.
>
> **ADR-007** (2026-08-01): Multimodal ingestion resolves ADR-001/ADR-002 as
> follows. **OCR** (REQ-P2-01, REQ-P2-03): a single call per image to
> Anthropic's vision-capable Messages API (`code/router/ingestion/ocr.py`),
> using forced tool-use (`tool_choice`) so the response is structured JSON
> (`has_readable_text`, `extracted_text`, `category`, `confidence`) rather
> than free-text parsing — this lets one paid call satisfy both REQ-P2-01
> (text extraction) and REQ-P2-03 (category classification) instead of two.
> **ASR** (REQ-P2-02): OpenAI's Whisper transcription API
> (`code/router/ingestion/asr.py`) called with `response_format="verbose_json"`,
> which returns per-segment `avg_logprob`/`no_speech_prob`; confidence is
> derived from those (mean of `exp(avg_logprob)` across segments, clamped to
> `[0, 1]`) rather than taken as an unexplained raw model output. Both
> clients are defined as `typing.Protocol` interfaces (`OCRClient`/
> `ASRClient`) so every test fakes them; no test in this project makes a
> live network call. `build_ocr_client()`/`build_asr_client()` read
> `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` from the environment; if a key is
> absent, the returned client raises `OCRClientError`/`ASRClientError` on
> first use rather than at import/construction time, so a key-less run still
> completes end-to-end — every media message just lands in the REQ-P2-04
> fallback path instead of halting the whole pipeline.
>
> `dataset/messages.csv` has 15 image rows and 8 voice rows out of 110; of
> those 15 image rows, every one still carries a non-blank `message_text`
> caption alongside the image — WhatsApp sends an image with an optional
> caption as one message, so `normalized_text` for an image row is the
> caption and the OCR transcript concatenated (`caption\ntranscript`) when
> both are present, not one replacing the other; OCR alone is used when
> there is no caption, and the caption alone is used if OCR fails (with
> `media_failure=true` still recording that the image content itself could
> not be read). `media_id` repeats across `messages.csv` +
> `message_history.csv` — `img_008` appears 4 times, `img_010`/`img_003` 3
> times each — so REQ-P2-05's caching requirement is load-bearing on this
> exact dataset, not a hypothetical; the cache is keyed by `media_id` and
> shared across one `run_media_ingestion` batch call. Every voice message
> gets the fixed `media_category = "voice_note"` (no classification call
> needed). The image taxonomy is `poster_promo | screenshot |
> document_photo | meme | personal_photo`, plus an `unclassified` fallback
> the vision model may return when a coarse bucket genuinely doesn't fit —
> never a fabricated or off-taxonomy string.

Every prompt in this phase inherits this ADR's tooling choice and design
decisions. Do not propose a local OCR/ASR stack, an unstructured free-text
parse of the vision response, or a second API call for image category
classification in place of the choices above — those alternatives were
already considered and rejected.

## Non-goals relevant to this phase (SPEC.md §3, verbatim subset)

- No custom model training or fine-tuning within the 24h window — OCR/ASR
  use off-the-shelf hosted APIs, not a trained classifier.
- No UI/dashboard — this is a batch scoring pipeline, CLI-invoked.
- No attempt to handle languages beyond what's present in the dataset
  without explicit evidence of need.

## Prompts in this phase, in dependency order

1. `REQ-P2-01-image-ocr-extraction.md` — `NormalizedMessage` contract,
   media lookup helpers, the `OCRClient` interface, and
   `AnthropicOCRClient`, wired so image messages' `normalized_text` combines
   the caption with the OCR transcript. Foundational: every later prompt in
   this phase builds on the module layout and error types this establishes.
2. `REQ-P2-02-voice-asr-transcription.md` — the `ASRClient` interface and
   `OpenAIWhisperASRClient`, wired so voice messages flow through the exact
   same `NormalizedMessage` assembly path as image/text messages — no
   forked downstream logic.
3. `REQ-P2-03-image-category-classification.md` — wires the `category`
   field already returned by the REQ-P2-01 OCR call into
   `NormalizedMessage.media_category`, validated against the fixed image
   taxonomy, plus the fixed `"voice_note"` category for voice messages.
4. `REQ-P2-04-media-failure-fallback.md` — the fallback contract: any
   `OCRClientError`/`ASRClientError`, any client-reported "no readable
   text"/"no speech detected" result, or any missing media file/record is
   caught and converted to `media_failure=true` with a lowered confidence
   and a populated `media_failure_reason` — never an unhandled exception,
   never a silent guess.
5. `REQ-P2-05-media-ingestion-caching.md` — `MediaIngestionCache`, keyed by
   `media_id` and shared across one `run_media_ingestion` batch call, so a
   `media_id` referenced by more than one message is ingested once; the
   batch entrypoint itself, wired into `code/main.py`.

Read `_PREAMBLE.md` (this file) before opening any prompt below. Execute
prompts in the listed order; each prompt's Definition of Done must pass
before starting the next.
