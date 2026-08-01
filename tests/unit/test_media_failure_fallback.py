"""Unit tests for explicit OCR/ASR fallback records."""

import pytest

from router.errors import ASRClientError, OCRClientError
from router.ingestion.asr import ASRResult
from router.ingestion.ocr import OCRResult
from router.ingestion.pipeline import normalize_message

from ingestion_fakes import FakeASRClient, FakeOCRClient


def _message(media_type: str, media_id: str, caption: str = "Caption") -> dict[str, object]:
    """Build a compact media row with all normalized-message passthrough fields."""
    return {
        "message_id": f"{media_type}_{media_id or 'missing'}",
        "user_id": "u_1",
        "conversation_type": "business",
        "group_id": "",
        "business_id": "business_1",
        "sender_user_id": "",
        "created_at": "2026-08-01 09:00",
        "message_text": caption,
        "media_type": media_type,
        "media_id": media_id,
        "forwarded_count": "0",
    }


@pytest.mark.parametrize(
    "media_id, expected_reason",
    [
        ("", "image message has no media_id"),
        ("img_missing", "no images.csv record found for media_id 'img_missing'"),
    ],
)
def test_image_reference_failures_preserve_caption_and_explain_the_fallback(
    load_fixture_bundle, fixtures_dir, media_id, expected_reason
):
    """Missing image references never discard known text or masquerade as successful OCR."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _message("image", media_id),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(),
        FakeASRClient(),
    )

    assert result.normalized_text == "Caption"
    assert result.media_failure is True
    assert result.media_confidence == 0.0
    assert result.media_failure_reason == expected_reason


def test_blank_ocr_output_is_a_low_confidence_failure_with_the_caption(load_fixture_bundle, fixtures_dir):
    """A model result without usable text cannot be treated as a successful image read."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _message("image", "img_test_001"),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(OCRResult(" ", 0.9, "meme", True, "no readable text")),
        FakeASRClient(),
    )

    assert result.normalized_text == "Caption"
    assert result.media_failure is True
    assert result.media_confidence == 0.2
    assert result.media_category == "meme"
    assert result.media_failure_reason == "no readable text"


@pytest.mark.parametrize(
    "media_id, expected_reason",
    [
        ("", "voice message has no media_id"),
        ("vn_missing", "no voice_notes.csv record found for media_id 'vn_missing'"),
    ],
)
def test_voice_reference_failures_produce_an_explicit_empty_transcript(
    load_fixture_bundle, fixtures_dir, media_id, expected_reason
):
    """Voice fallback is clear about missing media and always retains its modality category."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _message("voice", media_id, caption=""),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(),
        FakeASRClient(),
    )

    assert result.normalized_text == ""
    assert result.media_failure is True
    assert result.media_confidence == 0.0
    assert result.media_category == "voice_note"
    assert result.media_failure_reason == expected_reason


def test_blank_asr_output_is_a_low_confidence_failure(load_fixture_bundle, fixtures_dir):
    """A garbled or silent ASR result is bounded to the fallback confidence ceiling."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _message("voice", "vn_test_001", caption=""),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(),
        FakeASRClient(ASRResult("", 0.73, True, "silent audio")),
    )

    assert result.media_failure is True
    assert result.media_confidence == 0.2
    assert result.media_failure_reason == "silent audio"


@pytest.mark.parametrize(
    "client, expected_reason",
    [
        (FakeOCRClient(error=OCRClientError("  ")), "OCR request failed"),
        (FakeOCRClient(OCRResult("", 0.0, None, True, " ")), "OCR produced no readable text"),
    ],
)
def test_image_fallback_replaces_blank_client_reasons(
    load_fixture_bundle, fixtures_dir, client, expected_reason
):
    """Failed image rows always carry a usable reason even when the client supplied none."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _message("image", "img_test_001"),
        bundle,
        fixtures_dir / "dataset_valid",
        client,
        FakeASRClient(),
    )

    assert result.media_failure is True
    assert result.media_failure_reason == expected_reason


@pytest.mark.parametrize(
    "client, expected_reason",
    [
        (FakeASRClient(error=ASRClientError("  ")), "ASR request failed"),
        (FakeASRClient(ASRResult("", 0.0, True, " ")), "ASR produced no usable transcript"),
    ],
)
def test_voice_fallback_replaces_blank_client_reasons(
    load_fixture_bundle, fixtures_dir, client, expected_reason
):
    """Failed voice rows always carry a usable reason even when the client supplied none."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _message("voice", "vn_test_001", caption=""),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(),
        client,
    )

    assert result.media_failure is True
    assert result.media_failure_reason == expected_reason
