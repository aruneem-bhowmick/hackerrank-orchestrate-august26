"""Transcribes voice messages via OpenAI's Whisper transcription API.

ADR-002/ADR-007 (SPEC.md §5): ASR calls Whisper with
response_format="verbose_json" so segment-level avg_logprob/no_speech_prob
are available to derive a grounded confidence, rather than inventing one.
"""

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import openai

from router.errors import ASRClientError

_DEFAULT_ASR_MODEL = "whisper-1"
_NO_SPEECH_PROB_FAILURE_CUTOFF = 0.6
"""If the mean no_speech_prob across every segment exceeds this, the audio
is treated as silent/unclear regardless of what text Whisper transcribed —
most of the audio was judged non-speech."""

_NO_SEGMENTS_REASON = "no speech segments detected in the audio"
_UNRELIABLE_SPEECH_REASON = "silent or unclear audio: no reliable speech detected"


@dataclass(frozen=True)
class ASRResult:
    """One ASR call's outcome.

    confidence is derived from Whisper's verbose_json segment data (see
    _confidence_from_segments), never an unexplained raw model output.
    """

    text: str
    confidence: float
    failure: bool
    failure_reason: str | None


class ASRClient(Protocol):
    """The ASR boundary every caller in this package depends on, never a concrete client."""

    def transcribe(self, audio_path: Path) -> ASRResult:
        """Run ASR on one audio file.

        Raises ASRClientError on any failure to obtain a response at all
        (missing key, network/API error, unreadable file, unparseable
        response) — never returns a fabricated ASRResult in that case.
        """
        ...


class OpenAIWhisperASRClient:
    """ASRClient backed by OpenAI's Whisper transcription API."""

    def __init__(self, api_key: str, model: str = _DEFAULT_ASR_MODEL) -> None:
        """Build a client bound to one OpenAI API key and model."""
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def transcribe(self, audio_path: Path) -> ASRResult:
        """Call the Whisper transcription API once for audio_path and derive an ASRResult."""
        try:
            with audio_path.open("rb") as handle:
                response = self._client.audio.transcriptions.create(
                    model=self._model, file=handle, response_format="verbose_json"
                )
        except OSError as exc:
            raise ASRClientError(f"Could not read audio file '{audio_path}': {exc}") from exc
        except openai.OpenAIError as exc:
            raise ASRClientError(
                f"Whisper ASR request failed for '{audio_path.name}': {exc}"
            ) from exc

        return _asr_result_from_response(response)


class _UnconfiguredASRClient:
    """ASRClient stand-in used when OPENAI_API_KEY is not set.

    Raises ASRClientError on first use rather than at import/construction
    time, so a key-less run still completes end to end — every voice
    message lands in the media-failure fallback path instead of halting
    the whole pipeline.
    """

    def transcribe(self, audio_path: Path) -> ASRResult:
        """Always raise: no ASR is possible without a configured API key."""
        raise ASRClientError("OPENAI_API_KEY is not set; cannot run ASR.")


def build_asr_client() -> ASRClient:
    """Return an OpenAIWhisperASRClient built from OPENAI_API_KEY, or an unconfigured fallback."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _UnconfiguredASRClient()
    return OpenAIWhisperASRClient(api_key=api_key)


def _segment_float(segment: object, field: str) -> float:
    """Return a finite numeric Whisper segment field or raise ASRClientError.

    Whisper's verbose response is an external boundary. A missing, null,
    non-numeric, or non-finite metric is malformed response data rather
    than an unexpected Python exception for callers to handle.
    """
    try:
        value = float(getattr(segment, field))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ASRClientError(
            f"Whisper verbose_json segment is missing a usable '{field}': {exc}"
        ) from exc
    if not math.isfinite(value):
        raise ASRClientError(f"Whisper verbose_json segment has a non-finite '{field}'.")
    return value


def _confidence_from_segments(segments: list[object]) -> float:
    """Mean of exp(avg_logprob) across segments, clamped to [0, 1]."""
    if not segments:
        return 0.0
    try:
        scores = [
            max(0.0, min(1.0, math.exp(_segment_float(segment, "avg_logprob"))))
            for segment in segments
        ]
    except OverflowError as exc:
        raise ASRClientError("Whisper verbose_json segment has an unusable 'avg_logprob'.") from exc
    return sum(scores) / len(scores)


def _mean_no_speech_prob(segments: list[object]) -> float:
    """Mean no_speech_prob across segments; 1.0 (fully non-speech) when there are none."""
    if not segments:
        return 1.0
    return sum(_segment_float(segment, "no_speech_prob") for segment in segments) / len(segments)


def _asr_result_from_response(response: object) -> ASRResult:
    """Parse a Whisper verbose_json response into an ASRResult."""
    try:
        segments = list(getattr(response, "segments", None) or [])
    except TypeError as exc:
        raise ASRClientError("Whisper verbose_json response has an invalid 'segments' value.") from exc
    raw_text = getattr(response, "text", None)
    if not isinstance(raw_text, str):
        raise ASRClientError("Whisper verbose_json response has a non-string 'text' value.")
    text = raw_text.strip()

    if not segments:
        return ASRResult(text="", confidence=0.0, failure=True, failure_reason=_NO_SEGMENTS_REASON)

    confidence = _confidence_from_segments(segments)
    unclear = _mean_no_speech_prob(segments) > _NO_SPEECH_PROB_FAILURE_CUTOFF

    if unclear or not text:
        return ASRResult(
            text="", confidence=confidence, failure=True, failure_reason=_UNRELIABLE_SPEECH_REASON
        )

    return ASRResult(text=text, confidence=confidence, failure=False, failure_reason=None)
