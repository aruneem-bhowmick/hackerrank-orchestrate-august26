"""Integration tests for mixed successful and failed media ingestion."""

from router.ingestion.asr import ASRResult
from router.ingestion.ocr import OCRResult
from router.ingestion.pipeline import run_media_ingestion

from ingestion_fakes import FakeASRClient, FakeOCRClient


def test_batch_continues_after_image_and_voice_failures(load_fixture_bundle, fixtures_dir):
    """One unusable item cannot prevent other media rows from receiving normalized output."""
    bundle = load_fixture_bundle("dataset_valid")
    image_row = bundle.messages.iloc[0].copy()
    image_row.update(
        {"message_id": "image_message", "media_type": "image", "media_id": "img_test_001"}
    )
    voice_row = bundle.messages.iloc[1].copy()
    voice_row.update(
        {
            "message_id": "voice_message",
            "media_type": "voice",
            "media_id": "vn_test_001",
            "message_text": "",
        }
    )
    bundle.messages.loc[0] = image_row
    bundle.messages.loc[1] = voice_row

    normalized = run_media_ingestion(
        bundle,
        fixtures_dir / "dataset_valid",
        FakeOCRClient(OCRResult("", 0.8, "poster_promo", True, "no readable text")),
        FakeASRClient(ASRResult("", 0.9, True, "silent audio")),
    )

    assert set(normalized) == {"image_message", "voice_message"}
    assert normalized["image_message"].media_failure is True
    assert normalized["image_message"].normalized_text == "Quick reminder about tomorrow."
    assert normalized["voice_message"].media_failure is True
    assert normalized["voice_message"].media_failure_reason == "silent audio"
