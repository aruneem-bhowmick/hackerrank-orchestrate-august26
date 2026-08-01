"""System tests for the assembled media ingestion batch entrypoint."""

import pandas as pd
import pytest

from router.errors import MediaIngestionError
from router.ingestion.ocr import OCRResult
from router.ingestion.pipeline import run_media_ingestion

from ingestion_fakes import FakeASRClient, FakeOCRClient


def test_batch_cache_reuses_one_ocr_result_for_repeated_media_ids(load_fixture_bundle, fixtures_dir):
    """Two messages sharing one media ID cost one underlying OCR extraction in a batch."""
    bundle = load_fixture_bundle("dataset_valid")
    first = bundle.messages.iloc[0].copy()
    first.update({"message_id": "image_one", "media_type": "image", "media_id": "img_test_001"})
    second = first.copy()
    second.update({"message_id": "image_two", "message_text": "Second caption"})
    bundle.messages = pd.DataFrame([first, second])
    ocr_client = FakeOCRClient(OCRResult("Shared OCR", 0.9, "poster_promo", False, None))

    normalized = run_media_ingestion(
        bundle, fixtures_dir / "dataset_valid", ocr_client, FakeASRClient()
    )

    assert len(normalized) == 2
    assert normalized["image_one"].normalized_text.endswith("Shared OCR")
    assert normalized["image_two"].normalized_text == "Second caption\nShared OCR"
    assert len(ocr_client.calls) == 1


def test_separate_batch_runs_do_not_leak_cached_results(load_fixture_bundle, fixtures_dir):
    """Each invocation has fresh cache scope while producing stable normalized results."""
    bundle = load_fixture_bundle("dataset_valid")
    row = bundle.messages.iloc[0].copy()
    row.update({"message_id": "image_one", "media_type": "image", "media_id": "img_test_001"})
    bundle.messages = pd.DataFrame([row])
    ocr_client = FakeOCRClient(OCRResult("Shared OCR", 0.9, "poster_promo", False, None))

    first = run_media_ingestion(bundle, fixtures_dir / "dataset_valid", ocr_client, FakeASRClient())
    second = run_media_ingestion(bundle, fixtures_dir / "dataset_valid", ocr_client, FakeASRClient())

    assert first == second
    assert len(ocr_client.calls) == 2


def test_batch_rejects_duplicate_message_ids_instead_of_silently_dropping_rows(
    load_fixture_bundle, fixtures_dir
):
    """Dictionary-based batch output cannot hide a duplicate input message ID."""
    bundle = load_fixture_bundle("dataset_valid")
    bundle.messages = pd.concat([bundle.messages, bundle.messages.iloc[[0]]], ignore_index=True)

    with pytest.raises(MediaIngestionError, match="duplicate message_id"):
        run_media_ingestion(bundle, fixtures_dir / "dataset_valid", FakeOCRClient(), FakeASRClient())
