"""Unit tests for Whisper response parsing and client construction."""

import math
from types import SimpleNamespace

import pytest

from router.errors import ASRClientError
from router.ingestion import asr
from router.ingestion.pipeline import normalize_message


def _response(text: str, segments: list[object]) -> SimpleNamespace:
    """Build the minimal verbose Whisper response consumed by the parser."""
    return SimpleNamespace(text=text, segments=segments)


def _segment(avg_logprob: float, no_speech_prob: float) -> SimpleNamespace:
    """Build one minimal Whisper segment for a deterministic parsing test."""
    return SimpleNamespace(avg_logprob=avg_logprob, no_speech_prob=no_speech_prob)


def test_asr_response_parser_derives_confidence_from_segment_log_probabilities():
    """Transcript confidence is calculated from model evidence and bounded to [0, 1]."""
    response = _response(
        "Schedule the meeting tomorrow.",
        [_segment(math.log(0.8), 0.1), _segment(math.log(0.6), 0.2)],
    )

    result = asr._asr_result_from_response(response)

    assert result.text == "Schedule the meeting tomorrow."
    assert result.confidence == pytest.approx(0.7)
    assert result.failure is False


@pytest.mark.parametrize(
    "segment",
    [SimpleNamespace(no_speech_prob=0.1), SimpleNamespace(avg_logprob=None, no_speech_prob=0.1)],
)
def test_asr_response_parser_maps_missing_or_null_segment_metrics_to_client_errors(segment):
    """Malformed verbose responses use the typed client error consumed by the pipeline."""
    with pytest.raises(ASRClientError, match="usable 'avg_logprob'"):
        asr._asr_result_from_response(_response("Transcript", [segment]))


def test_voice_normalization_turns_a_malformed_asr_response_into_a_fallback(
    load_fixture_bundle, fixtures_dir
):
    """A parser error from the ASR boundary cannot abort normalization of the voice row."""
    bundle = load_fixture_bundle("dataset_valid")

    class MalformedResponseClient:
        """ASR test double whose response parser encounters a missing required metric."""

        def transcribe(self, audio_path):
            """Parse malformed verbose data through the same client-side response parser."""
            return asr._asr_result_from_response(
                _response("Transcript", [SimpleNamespace(no_speech_prob=0.1)])
            )

    message = {
        "message_id": "voice_malformed",
        "user_id": "u_1",
        "conversation_type": "personal",
        "group_id": "",
        "business_id": "",
        "sender_user_id": "u_2",
        "created_at": "2026-08-01 10:00",
        "message_text": "",
        "media_type": "voice",
        "media_id": "vn_test_001",
        "forwarded_count": "0",
    }

    result = normalize_message(
        message,
        bundle,
        fixtures_dir / "dataset_valid",
        object(),
        MalformedResponseClient(),
    )

    assert result.media_failure is True
    assert result.media_confidence == 0.0
    assert result.normalized_text == ""
    assert result.media_failure_reason is not None


@pytest.mark.parametrize(
    "response, expected_reason",
    [
        (_response("anything", []), "no speech segments detected in the audio"),
        (
            _response("could be noise", [_segment(math.log(0.8), 0.8)]),
            "silent or unclear audio: no reliable speech detected",
        ),
        (
            _response("", [_segment(math.log(0.8), 0.1)]),
            "silent or unclear audio: no reliable speech detected",
        ),
    ],
)
def test_asr_response_parser_marks_silent_or_unclear_audio_as_failure(response, expected_reason):
    """No segments, unreliable speech, and blank text all produce an explicit fallback."""
    result = asr._asr_result_from_response(response)

    assert result.failure is True
    assert result.text == ""
    assert result.failure_reason == expected_reason


def test_openai_client_requests_verbose_json_and_parses_the_transcript(monkeypatch, tmp_path):
    """The concrete API boundary asks Whisper for the segment detail needed by the contract."""
    audio_path = tmp_path / "voice.mp3"
    audio_path.write_bytes(b"audio-bytes")
    recorded: dict[str, object] = {}

    class Transcriptions:
        """Minimal recording endpoint for validating the request without a network call."""

        def create(self, **kwargs):
            """Record the request and return a response with one reliable segment."""
            recorded.update(kwargs)
            return _response("Voice content", [_segment(math.log(0.9), 0.1)])

    class Client:
        """Replacement OpenAI client exposing the expected audio endpoint tree."""

        def __init__(self, api_key):
            """Record the environment-derived key passed to the concrete client."""
            recorded["api_key"] = api_key
            self.audio = SimpleNamespace(transcriptions=Transcriptions())

    monkeypatch.setattr(asr.openai, "OpenAI", Client)
    result = asr.OpenAIWhisperASRClient("test-key").transcribe(audio_path)

    assert result.text == "Voice content"
    assert recorded["api_key"] == "test-key"
    assert recorded["model"] == "whisper-1"
    assert recorded["response_format"] == "verbose_json"


def test_build_asr_client_without_a_key_defers_failure_to_transcription(monkeypatch, tmp_path):
    """A missing key fails one voice item without preventing batch startup."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ASRClientError, match="OPENAI_API_KEY"):
        asr.build_asr_client().transcribe(tmp_path / "missing.mp3")
