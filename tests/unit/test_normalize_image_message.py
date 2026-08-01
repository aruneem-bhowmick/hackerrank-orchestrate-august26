"""Unit tests for image normalization and caption preservation."""

from router.errors import OCRClientError
from router.ingestion.ocr import OCRResult
from router.ingestion.pipeline import normalize_message

from ingestion_fakes import FakeASRClient, FakeOCRClient


def _image_message(**overrides) -> dict[str, object]:
    """Build one image row matching the messages.csv columns."""
    message: dict[str, object] = {
        "message_id": "img_message",
        "user_id": "u_1",
        "conversation_type": "business",
        "group_id": "",
        "business_id": "business_1",
        "sender_user_id": "",
        "created_at": "2026-08-01 09:00",
        "message_text": "Caption offer",
        "media_type": "image",
        "media_id": "img_test_001",
        "forwarded_count": "0",
    }
    message.update(overrides)
    return message


def test_image_normalization_concatenates_caption_and_ocr_text(load_fixture_bundle, fixtures_dir):
    """Image content augments the WhatsApp caption rather than replacing it."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _image_message(),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(OCRResult("Read this poster", 0.81, "poster_promo", False, None)),
        FakeASRClient(),
    )

    assert result.normalized_text == "Caption offer\nRead this poster"
    assert result.media_confidence == 0.81
    assert result.media_category == "poster_promo"
    assert result.media_failure is False


def test_image_normalization_uses_ocr_text_when_there_is_no_caption(load_fixture_bundle, fixtures_dir):
    """An image without a caption still has usable downstream text from OCR."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _image_message(message_text=""),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(OCRResult("Poster-only text", 0.7, "document_photo", False, None)),
        FakeASRClient(),
    )

    assert result.normalized_text == "Poster-only text"
    assert result.media_failure is False


def test_image_normalization_preserves_caption_when_ocr_client_raises(load_fixture_bundle, fixtures_dir):
    """An OCR outage records the fallback without discarding native message text."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _image_message(),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(error=OCRClientError("service unavailable")),
        FakeASRClient(),
    )

    assert result.normalized_text == "Caption offer"
    assert result.media_failure is True
    assert result.media_confidence == 0.0
    assert result.media_failure_reason == "service unavailable"


def test_image_normalization_discards_off_taxonomy_categories(load_fixture_bundle, fixtures_dir):
    """Model-provided categories cannot leak beyond the fixed internal contract."""
    bundle = load_fixture_bundle("dataset_valid")
    result = normalize_message(
        _image_message(),
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(OCRResult("Text", 0.5, "invoice", False, None)),
        FakeASRClient(),
    )

    assert result.media_category is None
