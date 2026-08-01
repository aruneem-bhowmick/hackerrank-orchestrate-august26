"""Unit tests for voice transcript normalization."""

from router.errors import ASRClientError
from router.ingestion.asr import ASRResult
from router.ingestion.pipeline import normalize_message

from ingestion_fakes import FakeASRClient, FakeOCRClient, make_message


def test_voice_normalization_uses_the_transcript_in_the_shared_message_shape(
    load_fixture_bundle, fixtures_dir
):
    """Voice messages emerge as NormalizedMessage records, not a separate downstream type."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        make_message(
            message_id="voice_message",
            conversation_type="personal",
            business_id="",
            sender_user_id="u_2",
            created_at="2026-08-01 10:00",
            message_text="",
            media_type="voice",
            media_id="vn_test_001",
        ),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(),
        FakeASRClient(ASRResult("Please call me back", 0.86, False, None)),
    )

    assert result.normalized_text == "Please call me back"
    assert result.media_category == "voice_note"
    assert result.media_confidence == 0.86
    assert result.media_failure is False


def test_voice_normalization_records_client_errors_as_a_low_confidence_fallback(
    load_fixture_bundle, fixtures_dir
):
    """An ASR client outage is explicit and cannot crash the message batch."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        make_message(
            message_id="voice_message",
            conversation_type="personal",
            business_id="",
            sender_user_id="u_2",
            created_at="2026-08-01 10:00",
            message_text="",
            media_type="voice",
            media_id="vn_test_001",
        ),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(),
        FakeASRClient(error=ASRClientError("transcription unavailable")),
    )

    assert result.normalized_text == ""
    assert result.media_failure is True
    assert result.media_confidence == 0.0
    assert result.media_failure_reason == "transcription unavailable"
    assert result.media_category == "voice_note"
