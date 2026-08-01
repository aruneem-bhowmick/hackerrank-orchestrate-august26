# REQ-P2-02 — Voice ASR Transcription

## Traceability
- Source requirement: REQ-P2-02 (SPEC.md §2, Phase 2)
- Depends on: REQ-P2-01 (`NormalizedMessage`, `media.py` lookup helpers,
  `pipeline.py`'s `normalize_message`/`_fallback_normalized_message`)
- Unblocks: REQ-P2-03 (voice's fixed category), REQ-P2-04, REQ-P2-05

## Objective
Every `media_type: voice` row in `dataset/messages.csv` must be run through
ASR, and the resulting transcript must flow through the *exact same*
downstream text handling as native text and OCR output — no forked logic.
This prompt builds the `ASRClient` interface and its OpenAI Whisper-backed
implementation, and replaces REQ-P2-01's `NotImplementedError` voice branch
in `normalize_message` with a real implementation that reuses
`_fallback_normalized_message` unchanged.

## Context & assumptions
- Read `_PREAMBLE.md` first; inherit the `NormalizedMessage` contract, the
  resolved ADR-002/ADR-007 (ASR engine choice), and the "same downstream
  pipeline as native text" requirement text verbatim.
- REQ-P2-01 already exists: `NormalizedMessage`, `lookup_media_file_path`
  (generic over `id_column` — reuse it as-is with `"voice_note_id"`),
  `_fallback_normalized_message`, and `normalize_message`'s text/image
  branches. Do not duplicate any of it.
- "No forked logic" means: once a voice message's transcript is obtained,
  it is assigned to `normalized_text` and the function returns exactly the
  same `NormalizedMessage` shape as a text or image message — there is no
  separate "voice normalized message" type, no separate downstream
  function signature, nothing that would require P3/P4 to special-case
  `media_type == "voice"` beyond reading the one shared contract.
- `voice_notes.csv`'s `message_text` is always blank for voice rows (per
  `problem_statement.md`'s input schema — voice messages carry no native
  caption), so there is no caption-concatenation case here unlike images;
  `normalized_text` is the transcript alone, or `""` on failure.
- `media_category` for voice messages is intentionally NOT introduced as a
  new lookup/classification step — assign the literal `"voice_note"`
  directly in this prompt's implementation (a private module constant is
  fine for now); REQ-P2-03 centralizes it into a shared `categories.py`
  alongside the image taxonomy and updates this module's import, but the
  *value* voice messages get does not change.
- ADR-002/ADR-007 (resolved): ASR is OpenAI's Whisper transcription API,
  called with `response_format="verbose_json"` so segment-level
  `avg_logprob`/`no_speech_prob` are available to derive a grounded
  confidence rather than inventing one. `OPENAI_API_KEY` is read from the
  environment only; never write a key into any file in this repo.

## Files to create or modify
- `code/router/errors.py` — modify: add `ASRClientError(MediaIngestionError)`.
- `code/router/ingestion/asr.py` — create: `ASRResult`, the `ASRClient`
  protocol, `OpenAIWhisperASRClient`, `build_asr_client`.
- `code/router/ingestion/pipeline.py` — modify: `normalize_message` gains an
  `asr_client: ASRClient` parameter and a real `_normalize_voice_message`
  implementation, replacing the `NotImplementedError` branch.
- `tests/fixtures/ingestion_audio/` — create: a tiny real MP3 fixture for
  tests needing a genuine file on disk.
- `tests/unit/test_asr_client.py` — create.
- `tests/unit/test_normalize_voice_message.py` — create.
- `tests/integration/test_asr_pipeline_integration.py` — create.

## Interfaces & signatures

```python
# code/router/ingestion/asr.py
@dataclass(frozen=True)
class ASRResult:
    """One ASR call's outcome. confidence is derived from Whisper's
    verbose_json segment data (see Implementation details), never an
    unexplained raw number."""
    text: str
    confidence: float
    failure: bool
    failure_reason: str | None

class ASRClient(Protocol):
    def transcribe(self, audio_path: Path) -> ASRResult:
        """Run ASR on one audio file. Raises ASRClientError on any failure
        to obtain a response at all (missing key, network/API error,
        unreadable file, unparseable response) — never returns a
        fabricated ASRResult in that case."""

class OpenAIWhisperASRClient:
    """ASRClient backed by OpenAI's Whisper transcription API."""
    def __init__(self, api_key: str, model: str = "whisper-1") -> None: ...
    def transcribe(self, audio_path: Path) -> ASRResult: ...

def build_asr_client() -> ASRClient:
    """Return an OpenAIWhisperASRClient built from OPENAI_API_KEY, or a
    client that raises ASRClientError("OPENAI_API_KEY is not set...") on
    first use if the key is absent — mirrors build_ocr_client's contract
    exactly."""
```

```python
# code/router/ingestion/pipeline.py (signature change)
def normalize_message(
    message: dict,
    bundle: DatasetBundle,
    dataset_dir: Path,
    ocr_client: OCRClient,
    asr_client: ASRClient,
) -> NormalizedMessage:
    """As REQ-P2-01, plus: media_type == "voice" now runs ASR via
    asr_client and returns a real NormalizedMessage instead of raising."""
```

## Implementation details
1. `OpenAIWhisperASRClient.transcribe`: open the file in binary mode and
   call `client.audio.transcriptions.create(model=self._model, file=handle,
   response_format="verbose_json")`. Wrap the file open and the API call in
   one `try/except` covering `OSError` and the OpenAI SDK's `OpenAIError`
   base class, re-raising both as `ASRClientError` with the audio file's
   name and the original exception chained (`from exc`).
2. Confidence derivation from the `TranscriptionVerbose` response: let
   `segments = getattr(response, "segments", None) or []`. If `segments` is
   empty, treat as failure (no speech detected at all) —
   `ASRResult(text="", confidence=0.0, failure=True, failure_reason=
   "no speech segments detected in the audio")`. Otherwise compute
   `confidence = mean(clamp(exp(seg.avg_logprob), 0, 1) for seg in
   segments)` and separately `mean_no_speech = mean(seg.no_speech_prob for
   seg in segments)`. If `mean_no_speech > _NO_SPEECH_PROB_FAILURE_CUTOFF`
   (module constant, `0.6` — most of the audio is judged non-speech) OR
   `response.text.strip()` is empty, return a failure `ASRResult` with
   `confidence` still set to the computed value (informative even on
   failure, mirroring `OCRResult`'s same convention) and
   `failure_reason="silent or unclear audio: no reliable speech detected"`.
   Otherwise return `ASRResult(text=response.text.strip(), confidence=...,
   failure=False, failure_reason=None)`.
3. `build_asr_client` mirrors `build_ocr_client` exactly: read
   `OPENAI_API_KEY` from the environment, empty → unconfigured client that
   always raises `ASRClientError("OPENAI_API_KEY is not set; cannot run
   ASR.")`, non-empty → `OpenAIWhisperASRClient(api_key=...)`.
4. `_normalize_voice_message(message, bundle, dataset_dir, asr_client)`:
   - Resolve `audio_path = lookup_media_file_path(media_id,
     bundle.voice_notes, "voice_note_id", dataset_dir)`.
   - If `audio_path is None`: `return _fallback_normalized_message(message,
     text="", reason=<"voice message has no media_id" or "no
     voice_notes.csv record found for media_id '<id>'">,
     category=_VOICE_NOTE_CATEGORY)` — note `text=""`, not the caption,
     since voice messages have no caption to fall back to.
   - Else call `asr_client.transcribe(audio_path)` inside
     `try/except ASRClientError as exc`; on the exception, build the same
     shape as a client-reported failure: `text=""`,
     `reason=str(exc)`, `confidence=0.0`.
   - On a successful `ASRResult` with `failure=True` (or blank text):
     `text=""`, `reason=result.failure_reason`,
     `confidence=min(result.confidence, _FAILURE_CONFIDENCE_CAP)` (reuse
     REQ-P2-01's `0.2` constant — import it, do not redefine a second
     magic number for the same concept).
   - On success: `text=result.text.strip()`, `media_failure=False`,
     `media_failure_reason=None`, `media_confidence=result.confidence`.
   - `media_category` is always `_VOICE_NOTE_CATEGORY` in every branch
     above (success or failure) — unlike the image path, a voice message's
     category is never unknown, only its transcript is.
5. `normalize_message`'s dispatch: `"voice"` now calls
   `_normalize_voice_message(message, bundle, dataset_dir, asr_client)`
   instead of raising. The `""`/`"image"` branches are unchanged from
   REQ-P2-01 except that `_normalize_image_message`'s call site now also
   receives the new `asr_client` parameter passed through unused (Python
   requires it in scope, not that every branch consumes it).

## Standards to apply
- Read `OPENAI_API_KEY` from the environment only; never write a key into
  any file in this repo.
- No AI attribution in code comments or docstrings.
- `OpenAIWhisperASRClient`/`build_asr_client` are the only place the
  `openai` SDK is imported in this module tree.
- `ASRClient` is a `typing.Protocol`; fakes in tests need no inheritance
  relationship to it.

## Test suite (exhaustive)
Framework: `pytest`. All OpenAI calls are faked via a hand-written
`FakeASRClient` implementing the `ASRClient` protocol — no test constructs a
real `OpenAIWhisperASRClient` against the network.
`tests/fixtures/ingestion_audio/tiny.mp3` is a small real MP3 checked into
the repo.

- **Unit:** `OpenAIWhisperASRClient.transcribe` against a monkeypatched
  OpenAI client double — well-formed verbose_json response with confident
  segments → correct `ASRResult`; empty `segments` → failure result with
  the "no speech segments" reason; high mean `no_speech_prob` → failure
  result; API exception → `ASRClientError` chained via `__cause__`;
  unreadable file path → `ASRClientError` (`test_asr_client.py`);
  `build_asr_client` with `OPENAI_API_KEY` set/unset
  (`test_asr_client.py`); `_normalize_voice_message`/`normalize_message`
  against a `FakeASRClient` — success, ASR-reported failure, raised
  `ASRClientError`, missing media_id, missing voice_notes.csv record, and
  confirming `media_category == "voice_note"` in every one of those cases
  (`test_normalize_voice_message.py`).
- **Integration:** `normalize_message` invoked against a loaded
  `DatasetBundle` fixture with a real `bundle.voice_notes` row pointing at
  the checked-in tiny MP3 fixture and a `FakeASRClient`
  (`test_asr_pipeline_integration.py`).
- **System:** N/A for this prompt — see REQ-P2-05 for the batch/system test.
- **Acceptance:** "the resulting transcript ... is then processed by the
  *same* downstream text pipeline as native text — no forked logic" →
  a dedicated assertion in `test_normalize_voice_message.py` that a
  transcribed voice message and a native text message with identical
  content produce `NormalizedMessage` instances differing only in
  `media_type`/`media_category`/`media_confidence` — same dataclass shape,
  same field set, `normalized_text` populated the same way.
- **Smoke:** `normalize_message` runs on one synthetic voice-message dict
  without raising.
- **Sanity:** a known-good audio fixture still transcribes to the same text
  after unrelated changes.
- **Regression:** none yet — REQ-P2-04 owns the fallback-shape regression
  suite across both OCR and ASR.
- **End-to-end:** N/A — see REQ-P2-01's identical justification; ADR-007
  scopes live-API e2e out of the automated suite.
- **API:** request/response shaping for the Whisper call — asserts
  `response_format="verbose_json"` is requested, and that a realistic
  verbose_json payload (with `segments`) parses into the exact `ASRResult`
  expected, including the `avg_logprob`/`no_speech_prob` → confidence
  arithmetic on at least two concrete numeric examples
  (`test_asr_client.py`).
- **UI:** N/A — no rendered surface (SPEC.md §3 Non-Goals).

## Acceptance criteria (derived from SPEC.md, made executable)
- "Every `media_type: voice` message MUST be run through ASR" → every
  voice-row test asserts the fake ASR client was called.
- "the resulting transcript ... feeds `normalized_text`" → success-case
  tests assert `normalized_text == result.text.strip()`.
- "processed by the *same* downstream text pipeline as native text — no
  forked logic" → the same-shape-as-text-message acceptance test above.

## Definition of Done
- All acceptance criteria pass.
- All applicable test types implemented (others marked N/A with reason).
- `normalize_message`'s output for a voice row matches the `NormalizedMessage`
  contract exactly, with no separate voice-specific type or shape.
- No change to a shared data contract in this prompt.

## Out of scope
- Wiring `media_category` through a shared taxonomy module (REQ-P2-03) —
  the literal value is correct now, its centralization is not this
  prompt's job.
- Any caching layer (REQ-P2-05).
- Wiring a batch entrypoint into `code/main.py` (REQ-P2-05).
