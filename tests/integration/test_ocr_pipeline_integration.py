"""Integration coverage for OCR results flowing into normalized messages."""

from router.ingestion.ocr import OCRResult
from router.ingestion.pipeline import run_media_ingestion

from ingestion_fakes import FakeASRClient, FakeOCRClient


def test_batch_ingestion_runs_ocr_for_an_image_row_and_keeps_text_rows(load_fixture_bundle, fixtures_dir):
    """The shared batch path produces a normalized record for every original row."""
    bundle = load_fixture_bundle("dataset_valid")
    image_row = bundle.messages.iloc[0].copy()
    image_row["message_id"] = "img_message"
    image_row["media_type"] = "image"
    image_row["media_id"] = "img_test_001"
    image_row["message_text"] = "Caption"
    bundle.messages.loc[0] = image_row
    client = FakeOCRClient(OCRResult("OCR body", 0.75, "screenshot", False, None))

    dataset_dir = fixtures_dir / "dataset_valid"
    normalized = run_media_ingestion(bundle, dataset_dir, client, FakeASRClient())

    assert len(normalized) == len(bundle.messages)
    assert normalized["img_message"].normalized_text == "Caption\nOCR body"
    assert normalized["msg_test_002"].normalized_text == "Special offer just for you!"
    assert client.calls == [dataset_dir / "media/images/img_test_001.jpg"]
