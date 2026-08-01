# REQ-P2-01 — Image OCR Extraction

## Traceability
- Source requirement: REQ-P2-01 (SPEC.md §2, Phase 2)
- Depends on: none (first prompt in this phase; depends only on the already-
  merged P0 `DatasetBundle`)
- Unblocks: REQ-P2-02, REQ-P2-03, REQ-P2-04, REQ-P2-05

## Objective
Every `media_type: image` row in `dataset/messages.csv` must be run through
OCR before routing, per `SPEC.md` §2 Phase 2. This prompt builds the
`NormalizedMessage` contract (§1.2, as amended by ADR-007), the media-file
lookup helpers both this and the voice path will reuse, the `OCRClient`
interface and its Anthropic-backed implementation, and the `normalize_message`
entrypoint's text and image branches — the foundation P2's remaining
requirements extend rather than replace.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the `NormalizedMessage` contract (§1.2),
  ADR-001/ADR-007 (OCR engine choice), and the dependency-ordered prompt list
  it carries.
- Consumes `DatasetBundle.messages` (one row per call) and
  `DatasetBundle.images` (to resolve `media_id` → `file_path`), plus a
  `dataset_dir: Path` the caller supplies (the directory `images.csv`'s
  `file_path` values are relative to — `code/main.py`'s existing
  `DEFAULT_DATASET_DIR`).
- `media_type == "voice"` is explicitly **out of scope** for this prompt.
  `normalize_message` raises `NotImplementedError` for it; REQ-P2-02 replaces
  that branch with a real implementation. Do not build any voice-handling
  logic here.
- `media_category` is intentionally left `None` for every image in this
  prompt, even though `OCRResult` already carries a `category` field (the
  Anthropic tool schema asks for it in the same call per ADR-007, to avoid a
  second paid call later) — REQ-P2-03 is what wires that field into
  `NormalizedMessage.media_category`. Do not populate `media_category` here.
- ADR-001/ADR-007 (resolved): OCR is Anthropic's vision-capable Messages API,
  called once per image with forced tool-use so the response is structured
  JSON, not free-text. `ANTHROPIC_API_KEY` is read from the environment only;
  never write a key into any file in this repo.

## Files to create or modify
- `code/router/errors.py` — modify: add `MediaIngestionError(DatasetError)`
  and `OCRClientError(MediaIngestionError)`.
- `code/router/ingestion/__init__.py` — create: package docstring only.
- `code/router/ingestion/message.py` — create: `NormalizedMessage`.
- `code/router/ingestion/media.py` — create: `resolve_media_path`,
  `lookup_media_file_path` (generic over `images.csv`/`voice_notes.csv` via
  an `id_column` parameter, so REQ-P2-02 reuses it unchanged for voice).
- `code/router/ingestion/ocr.py` — create: `OCRResult`, the `OCRClient`
  protocol, `AnthropicOCRClient`, `build_ocr_client`.
- `code/router/ingestion/pipeline.py` — create: `normalize_message`,
  `_normalize_text_message`, `_normalize_image_message`,
  `_fallback_normalized_message`.
- `tests/fixtures/ingestion_images/` — create: a tiny real JPEG fixture (a
  few KB, synthetic) for tests that need a real file on disk without
  depending on `dataset/media/`.
- `tests/unit/test_normalized_message_contract.py` — create.
- `tests/unit/test_media_lookup.py` — create.
- `tests/unit/test_ocr_client.py` — create.
- `tests/unit/test_normalize_image_message.py` — create.
- `tests/integration/test_ocr_pipeline_integration.py` — create.

## Interfaces & signatures

```python
# code/router/ingestion/message.py
@dataclass(frozen=True)
class NormalizedMessage:
    """The Normalized Message contract from SPEC.md §1.2, as amended by ADR-007."""
    message_id: str
    user_id: str
    conversation_type: str
    group_id: str
    business_id: str
    sender_user_id: str
    created_at: str
    media_type: str
    normalized_text: str
    media_confidence: float
    media_failure: bool
    media_category: str | None
    media_failure_reason: str | None
```

```python
# code/router/ingestion/media.py
def resolve_media_path(dataset_dir: Path, relative_path: str) -> Path:
    """Join dataset_dir with a file_path value from images.csv/voice_notes.csv."""

def lookup_media_file_path(
    media_id: str, media_table: pd.DataFrame, id_column: str, dataset_dir: Path
) -> Path | None:
    """Resolve media_id to an absolute Path via media_table, or None if
    media_id is blank or has no matching row. Never raises for a missing
    record — a missing record is a normal, expected input this function's
    caller must handle, not this function's error to surface."""
```

```python
# code/router/ingestion/ocr.py
@dataclass(frozen=True)
class OCRResult:
    """One OCR call's outcome. category/confidence are always present even
    when failure=True — a model may say "no readable text" while still
    offering a category guess and a low confidence, and both are still
    useful signal, not noise to discard."""
    text: str
    confidence: float
    category: str | None
    failure: bool
    failure_reason: str | None

class OCRClient(Protocol):
    def extract(self, image_path: Path) -> OCRResult:
        """Run OCR (and category classification) on one image file.
        Raises OCRClientError on any failure to obtain a response at all
        (missing key, network/API error, malformed image, unparseable
        response) — never returns a fabricated OCRResult in that case."""

class AnthropicOCRClient:
    """OCRClient backed by Anthropic's vision-capable Messages API."""
    def __init__(self, api_key: str, model: str = "claude-sonnet-5") -> None: ...
    def extract(self, image_path: Path) -> OCRResult: ...

def build_ocr_client() -> OCRClient:
    """Return an AnthropicOCRClient built from ANTHROPIC_API_KEY, or a
    client that raises OCRClientError("ANTHROPIC_API_KEY is not set...")
    on first use if the key is absent — never at import or construction
    time, so a key-less run only fails per-message (REQ-P2-04), not
    globally."""
```

```python
# code/router/ingestion/pipeline.py
def normalize_message(
    message: dict, bundle: DatasetBundle, dataset_dir: Path, ocr_client: OCRClient
) -> NormalizedMessage:
    """Normalize one messages.csv row (as a dict, e.g. from
    bundle.messages.to_dict("records")) to a NormalizedMessage. Dispatches
    on media_type: "" -> pass message_text through unchanged; "image" ->
    OCR extraction combined with the caption; "voice" -> raises
    NotImplementedError until REQ-P2-02 lands. Never raises for a
    well-formed image row regardless of OCR outcome — see REQ-P2-04's
    fallback contract, implemented here and locked down by that prompt's
    tests."""
```

## Implementation details
1. `NormalizedMessage` is frozen and field-for-field matches §1.2 as amended;
   no defaults — every field is always explicitly supplied by its
   constructor call site, so a missing value is a `TypeError` at
   construction, not a silently blank field downstream.
2. `lookup_media_file_path` filters `media_table[id_column] == media_id`
   and returns `resolve_media_path(dataset_dir, row["file_path"])` for the
   first match, or `None` if `media_id` is falsy or has zero matches. Do not
   raise on zero matches or on duplicate matches (take the first, matching
   `_lookup_business`'s existing "first match" convention in
   `code/router/safety/gate.py`).
3. `OCRClient.extract` (Anthropic implementation): read the image bytes,
   base64-encode them, and call `messages.create` with `max_tokens`, a
   single user message whose `content` is an image block
   (`{"type": "image", "source": {"type": "base64", "media_type": ...,
   "data": ...}}`) followed by a text instruction block, `tools=[<one tool
   named e.g. "submit_image_analysis">]`, and
   `tool_choice={"type": "tool", "name": <that name>}` so the reply is
   always the structured tool call, never free text to parse. The tool's
   `input_schema` requires `has_readable_text: bool`, `extracted_text:
   string`, `category: string` (enum-constrained to the 6 taxonomy values —
   define them locally in this module for now; REQ-P2-03 centralizes them
   in a new `categories.py` and this module imports from there instead),
   and `confidence: number` (0–1). Guess the image's MIME type from its
   extension (`mimetypes.guess_type`), defaulting to `"image/jpeg"`.
4. Wrap the whole call (byte read, API call, response parse) in one
   `try/except` covering `OSError` (unreadable file) and the Anthropic
   SDK's `APIError` base class; re-raise both as `OCRClientError` with the
   image's filename and the original exception chained (`from exc`) so the
   underlying cause is never swallowed. If the tool-use block is missing
   from the response (defensive — should not happen with `tool_choice`
   forced, but never assume an external API's shape), raise
   `OCRClientError` rather than crash on a `KeyError`/`AttributeError`.
5. Map the parsed payload to `OCRResult`: `text = extracted_text`,
   `confidence` clamped to `[0, 1]`, `category` passed through as-is
   (unvalidated here — REQ-P2-03's `validate_image_category` does that),
   `failure = not has_readable_text or not extracted_text.strip()`,
   `failure_reason` set to a fixed description
   ("the vision model found no readable text in the image") when
   `failure` is true, else `None`.
6. `build_ocr_client` reads `os.environ.get("ANTHROPIC_API_KEY", "").strip()`.
   Empty → return an unconfigured client whose `extract` always raises
   `OCRClientError("ANTHROPIC_API_KEY is not set; cannot run OCR.")`.
   Non-empty → `AnthropicOCRClient(api_key=...)`.
7. `_normalize_text_message(message)`: `normalized_text = message_text`,
   `media_confidence = 1.0`, `media_failure = False`, `media_category =
   None`, `media_failure_reason = None`. Every other `NormalizedMessage`
   field copies straight from `message`.
8. `_normalize_image_message(message, bundle, dataset_dir, ocr_client)`:
   - Resolve `image_path = lookup_media_file_path(media_id, bundle.images,
     "image_id", dataset_dir)` (skip the lookup and treat as not-found if
     `media_id` is blank).
   - If `image_path is None`: return `_fallback_normalized_message(message,
     text=message_text, reason=<"image message has no media_id" or
     "no images.csv record found for media_id '<id>'">, category=None)`.
   - Else call `ocr_client.extract(image_path)` inside a `try/except
     OCRClientError as exc`; on the exception, treat it exactly like a
     client-reported failure: `text=message_text`, `reason=str(exc)`,
     `category=None`, `confidence=0.0`.
   - On a successful `OCRResult` with `failure=True` (or blank text):
     `text=message_text` (caption alone), `reason=result.failure_reason`,
     `category=None` (unused until REQ-P2-03), `confidence=min(result.confidence,
     0.2)` — see REQ-P2-04's prompt for why 0.2 and the named constant it
     introduces; for this prompt, inline a private
     `_FAILURE_CONFIDENCE_CAP = 0.2` module constant with a one-line comment,
     REQ-P2-04 does not need to change this value, only test it exhaustively.
   - On a successful `OCRResult` with usable text: `text =
     f"{caption}\n{result.text.strip()}".strip()` if the caption is
     non-blank, else `result.text.strip()`; `media_failure=False`;
     `media_failure_reason=None`; `media_confidence=result.confidence`;
     `media_category=None` (still unused this prompt).
9. `_fallback_normalized_message(message, text, reason, category)`: the one
   shared constructor for every "could not ingest" path — sets
   `media_failure=True`, `media_confidence=0.0`,
   `media_failure_reason=reason`, `media_category=category`,
   `normalized_text=text`, copying every other field from `message`. Both
   this prompt's image path and REQ-P2-02's voice path call it for the
   "no media record found" case, so build it generically now.
10. `normalize_message` reads `media_type = message.get("media_type", "") or
    ""`, stripped. `"image"` → `_normalize_image_message(...)`. `"voice"` →
    `raise NotImplementedError("voice message ingestion lands in
    REQ-P2-02")`. Anything else (including `""`) → `_normalize_text_message(message)`.

## Standards to apply
- Read `ANTHROPIC_API_KEY` from the environment only; never write a key into
  any file in this repo.
- No AI attribution in code comments or docstrings.
- `AnthropicOCRClient`/`build_ocr_client` are the only place the `anthropic`
  SDK is imported in this module tree — keep the boundary narrow so tests
  never need the real SDK or network access.
- `OCRClient` is a `typing.Protocol`, not an ABC — fakes in tests need no
  inheritance relationship to it, just a matching `extract` method.

## Test suite (exhaustive)
Framework: `pytest`. External Anthropic calls are always faked via a
hand-written `FakeOCRClient` implementing the `OCRClient` protocol (a plain
class with an `extract` method returning a canned `OCRResult` or raising
`OCRClientError`) — no test constructs a real `AnthropicOCRClient` against
the network. `tests/fixtures/ingestion_images/tiny.jpg` is a small real
JPEG checked into the repo for tests that need a genuine file on disk.

- **Unit:** `NormalizedMessage` field-for-field construction and
  frozen/immutability (`test_normalized_message_contract.py`);
  `lookup_media_file_path` — match found, no match, blank media_id, and
  first-match-wins on a duplicated `image_id`
  (`test_media_lookup.py`); `AnthropicOCRClient.extract` against a
  monkeypatched Anthropic client double — well-formed tool-use response →
  correct `OCRResult`; missing tool-use block → `OCRClientError`; API
  exception → `OCRClientError` with the original chained via `__cause__`;
  unreadable file path → `OCRClientError` (`test_ocr_client.py`);
  `build_ocr_client` with `ANTHROPIC_API_KEY` set/unset via
  `monkeypatch.setenv`/`delenv` (`test_ocr_client.py`);
  `_normalize_image_message`/`normalize_message` against a `FakeOCRClient`
  — caption+OCR concatenation, OCR-only (no caption), caption-only
  (OCR failure), missing media_id, missing images.csv record, `voice`
  raises `NotImplementedError` (`test_normalize_image_message.py`).
- **Integration:** `normalize_message` invoked against a loaded
  `DatasetBundle` fixture (via `load_fixture_bundle`) with a real
  `bundle.images` row pointing at the checked-in tiny JPEG fixture and a
  `FakeOCRClient`, confirming the media lookup + OCR + pipeline layers
  compose correctly end to end for one image message
  (`test_ocr_pipeline_integration.py`).
- **System:** N/A for this prompt — no batch entrypoint exists yet; REQ-P2-05
  builds `run_media_ingestion` and owns the phase-level system test.
- **Acceptance:** "every image message MUST be run through OCR before
  routing" → `test_normalize_image_message.py` asserts `FakeOCRClient.extract`
  is actually invoked (call-count assertion) for an image row, and that its
  returned text reaches `normalized_text`.
- **Smoke:** `normalize_message` runs on one synthetic image-message dict
  and one synthetic text-message dict without raising, each producing a
  `NormalizedMessage`.
- **Sanity:** a known-good image+caption fixture still concatenates
  caption-then-OCR-text in that order after unrelated changes.
- **Regression:** none yet — REQ-P2-04 is where fallback-shape regression
  fixtures get locked in, since fallback behavior is this prompt's
  implementation detail but that prompt's dedicated contract.
- **End-to-end:** N/A for this prompt — gated live-API e2e (real
  `ANTHROPIC_API_KEY`, real network) is out of scope for the automated
  suite entirely per ADR-007; this project's e2e coverage is the local
  full-pipeline run over `dataset/messages.csv`, which REQ-P2-05's system
  test exercises with fakes.
- **API:** request/response shaping for the Anthropic call — asserts the
  outgoing `messages.create` call includes the image content block,
  `tool_choice` forcing the OCR tool, and that a realistic tool-use
  response payload parses into the exact `OCRResult` expected; a
  malformed/incomplete tool-use payload (missing `extracted_text`) is
  handled as `OCRClientError`, not a `KeyError` (`test_ocr_client.py`).
- **UI:** N/A — no rendered surface (SPEC.md §3 Non-Goals); `normalized_text`
  is consumed by later phases, not read directly by a person at this stage.

## Acceptance criteria (derived from SPEC.md, made executable)
- "Every `media_type: image` message MUST be run through OCR before
  routing" → every image-row test asserts the fake OCR client was called.
- "the resulting text (if any) feeds `normalized_text`" → concatenation/
  fallback tests assert the exact `normalized_text` value for each case
  (both-present, OCR-only, caption-only).
- `NormalizedMessage` field names/types match §1.2 exactly, including the
  ADR-007 `media_failure_reason` addition → `test_normalized_message_contract.py`.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- `NormalizedMessage` matches the SPEC.md §1.2 contract (as amended)
  exactly.
- No further change to a shared data contract beyond the ADR-007 extension
  already authorized in SPEC.md.

## Out of scope
- Voice/ASR handling (REQ-P2-02).
- Wiring `media_category` into the output (REQ-P2-03).
- Any caching layer (REQ-P2-05) — this prompt calls `ocr_client.extract`
  unconditionally, once per call, with no dedup.
- Wiring `normalize_message`/a batch entrypoint into `code/main.py`
  (REQ-P2-05).
