# REQ-P2-03 — Image Category Classification

## Traceability
- Source requirement: REQ-P2-03 (SPEC.md §2, Phase 2)
- Depends on: REQ-P2-01 (`OCRResult.category`, `ocr.py`'s local taxonomy),
  REQ-P2-02 (voice's inline `_VOICE_NOTE_CATEGORY` literal in `pipeline.py`)
- Unblocks: REQ-P2-04 (the fallback contract test matrix asserts
  `media_category` alongside the other fields), REQ-P2-05

## Objective
`media_category` is part of the `NormalizedMessage` contract (§1.2) but has
been left `None` for every image so far, and voice's `"voice_note"` value
has lived as a private literal inline in `pipeline.py`. This prompt gives
the taxonomy a single source of truth (`categories.py`), wires the OCR
call's already-returned `category` field into `NormalizedMessage.media_category`
for images (validated against the fixed taxonomy — never a fabricated or
off-taxonomy string), and points voice's category assignment at the same
module. No new external call is introduced — REQ-P2-01's OCR call already
asked for `category` in the same tool-use response as `extracted_text`,
per ADR-007, specifically so this requirement would not need a second paid
call per image.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the `NormalizedMessage` contract and
  ADR-007's taxonomy: `poster_promo | screenshot | document_photo | meme |
  personal_photo | unclassified` for images, `voice_note` fixed for voice.
- `OCRResult.category` (from REQ-P2-01) is the raw string the Anthropic tool
  call returned, already enum-constrained by the tool schema — but this
  prompt does not trust that constraint blindly; `validate_image_category`
  re-checks it against the same taxonomy independently, so a future
  loosening of the tool schema (or a model deviating from it) cannot leak
  an off-taxonomy string into `NormalizedMessage.media_category`.
- REQ-P2-02 already assigns voice messages a category via a private
  `_VOICE_NOTE_CATEGORY` constant inside `pipeline.py` — this prompt
  replaces that with an import from the new `categories.py`, without
  changing the value or any voice-path test's expected output.

## Files to create or modify
- `code/router/ingestion/categories.py` — create: `IMAGE_CATEGORIES`,
  `VOICE_NOTE_CATEGORY`, `validate_image_category`.
- `code/router/ingestion/ocr.py` — modify: import `IMAGE_CATEGORIES` from
  `categories.py` instead of defining a local `_OCR_CATEGORIES` tuple, for
  the tool schema's `category` enum constraint.
- `code/router/ingestion/pipeline.py` — modify: `_normalize_image_message`
  now sets `media_category = validate_image_category(ocr_result.category)`
  in place of the hardcoded `None`s from REQ-P2-01; `_normalize_voice_message`
  and the missing-media-record fallback path now import
  `categories.VOICE_NOTE_CATEGORY` instead of the private literal.
- `tests/unit/test_image_category_classification.py` — create.

## Interfaces & signatures

```python
# code/router/ingestion/categories.py
IMAGE_CATEGORIES: frozenset[str] = frozenset({
    "poster_promo", "screenshot", "document_photo", "meme", "personal_photo",
    "unclassified",
})
"""The fixed coarse taxonomy for media_category on image messages, per
REQ-P2-03's example list plus an "unclassified" catch-all the vision model
may return when no bucket genuinely fits. Never extend this set to match a
model's off-taxonomy output — see validate_image_category."""

VOICE_NOTE_CATEGORY: str = "voice_note"
"""The fixed media_category value for every media_type == "voice" message —
there is only one voice sub-type, unlike images' five, so no classification
call is needed."""

def validate_image_category(raw: str | None) -> str | None:
    """Return raw if it is a member of IMAGE_CATEGORIES (case-sensitive,
    exact match), else None. Never invents or coerces an unrecognized value
    into "unclassified" or any other member — an off-taxonomy response is
    treated the same as "no category available", per REQ-P2-04's "never
    silently guess" contract one requirement over."""
```

## Implementation details
1. `IMAGE_CATEGORIES` and `VOICE_NOTE_CATEGORY` are the single source of
   truth; no other module defines its own copy of either after this prompt
   lands.
2. `validate_image_category(raw)`: `return raw if raw in IMAGE_CATEGORIES
   else None`. Handles `raw is None` naturally (`None not in
   IMAGE_CATEGORIES`). Pure function, no I/O, trivially unit-testable.
3. `ocr.py`'s tool schema (`_OCR_TOOL_SCHEMA`'s `category` property) now
   builds its `enum` list from `sorted(IMAGE_CATEGORIES)` instead of a
   locally duplicated tuple. The API request shape does not otherwise
   change — this is a refactor of where the constant lives, not a schema
   redesign.
4. `_normalize_image_message`: in the "successful `OCRResult` with usable
   text" branch, set `media_category = validate_image_category(ocr_result.category)`
   instead of `None`. In the "OCR failed/blank text" branch, also set
   `media_category = validate_image_category(ocr_result.category)` — a
   model can say "no readable text" while still confidently observing
   "this looks like a personal photo," and that is still useful signal for
   P4's `message_type` inference, not something to discard just because
   OCR text extraction itself failed. Only the "no media record found" /
   `OCRClientError` fallback paths (where no model response exists at all)
   get `media_category = None`.
5. `_normalize_voice_message` and the voice "no media record" fallback:
   replace the private `_VOICE_NOTE_CATEGORY` literal with
   `categories.VOICE_NOTE_CATEGORY`. Delete the now-unused private constant
   from `pipeline.py`.

## Standards to apply
- No AI attribution in code comments or docstrings.
- `categories.py` has no I/O and no dependency on `ocr.py`/`asr.py`/
  `pipeline.py` — it is imported by all three, never the reverse, so there
  is no import cycle.

## Test suite (exhaustive)
Framework: `pytest`. No external calls in this prompt's own logic; existing
`FakeOCRClient`/`FakeASRClient` fakes from REQ-P2-01/02 are reused and
extended with category values.

- **Unit:** `validate_image_category` — every member of `IMAGE_CATEGORIES`
  passes through unchanged; `None` → `None`; an arbitrary off-taxonomy
  string (e.g. `"screenshot!!"`, `"receipt"`) → `None`; empty string →
  `None`. `_normalize_image_message` with a `FakeOCRClient` returning each
  of the 6 taxonomy values in turn → `NormalizedMessage.media_category`
  equals that value; returning an off-taxonomy string → `None`, not the raw
  string. `_normalize_voice_message` and the missing-media-record voice
  fallback → `media_category == "voice_note"` in both
  (`test_image_category_classification.py`).
- **Integration:** `ocr.py`'s tool schema construction includes exactly
  `sorted(IMAGE_CATEGORIES)` as the `category` property's enum — a
  monkeypatched-client test asserting the request payload shape, extending
  `test_ocr_client.py` from REQ-P2-01 rather than duplicating a new file.
- **System:** N/A — see REQ-P2-05.
- **Acceptance:** "Image messages MUST be classified into a coarse
  `media_category`" → the six-taxonomy-values unit test above, run for
  every value, is the direct check.
- **Smoke:** classifying one synthetic image message with a valid
  fake-returned category produces a non-`None` `media_category`.
- **Sanity:** a known-good "poster_promo"-categorized fixture still
  classifies the same way after unrelated changes.
- **Regression:** a fixture locking that an off-taxonomy model response
  never leaks through as `media_category` — this is exactly the kind of
  silent-drift bug a taxonomy change could reintroduce later, so pin it.
- **End-to-end:** N/A — see REQ-P2-01's identical justification.
- **API:** N/A for `categories.py` itself (pure logic, no external call);
  the tool-schema-shape assertion above is covered under Integration
  instead, since it is a request-shaping detail of the already-existing
  `ocr.py` API boundary, not a new one.
- **UI:** N/A — no rendered surface (SPEC.md §3 Non-Goals); `media_category`
  is consumed by P4's `message_type` inference, not read directly by a
  person at this stage.

## Acceptance criteria (derived from SPEC.md, made executable)
- "Image messages MUST be classified into a coarse `media_category`" →
  every `IMAGE_CATEGORIES` member round-trips through
  `_normalize_image_message` unchanged.
- The category list matches REQ-P2-03's example (poster/promo, screenshot,
  document photo, meme, personal photo) plus the documented
  `unclassified` addition → `IMAGE_CATEGORIES` contents test.
- No off-taxonomy string ever reaches `NormalizedMessage.media_category` →
  the regression fixture above.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- `categories.py` is the sole definition site for both taxonomies; `ocr.py`
  and `pipeline.py` import from it, no duplicated constants remain.
- No change to a shared data contract in this prompt (`media_category`'s
  type was already `str | null` in §1.2; this prompt only starts
  populating it correctly).

## Out of scope
- The fallback contract itself (REQ-P2-04) — this prompt only ensures
  `media_category` behaves correctly within the success/failure branches
  REQ-P2-01/02 already built; it does not add new failure-handling paths.
- Any caching layer (REQ-P2-05).
