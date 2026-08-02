"""Integration coverage for OCR/ASR cache sharing across main.py's two routing passes."""

import pandas as pd

from router.ingestion.cache import CachingASRClient, CachingOCRClient
from router.ingestion.ocr import OCRResult

from ingestion_fakes import FakeASRClient, FakeOCRClient

import main


def test_production_and_calibration_passes_share_one_ocr_cache(load_fixture_bundle, fixtures_dir):
    """A media_id present in both messages.csv and sample_messages.csv is only OCR'd once."""
    bundle = load_fixture_bundle("dataset_valid")
    bundle.messages = pd.DataFrame(
        [
            {
                "message_id": "msg_test_001",
                "user_id": "u_001",
                "conversation_type": "group",
                "group_id": "group_001",
                "business_id": "",
                "sender_user_id": "u_002",
                "created_at": "2026-07-31 09:00",
                "message_text": "Reminder photo",
                "media_type": "image",
                "media_id": "img_test_001",
                "forwarded_count": "0",
            }
        ]
    )
    bundle.sample_messages = pd.DataFrame(
        [
            {
                "message_id": "sample_test_001",
                "user_id": "u_001",
                "conversation_type": "group",
                "group_id": "group_001",
                "business_id": "",
                "sender_user_id": "u_002",
                "created_at": "2026-07-30 09:00",
                "message_text": "Sample reminder photo",
                "media_type": "image",
                "media_id": "img_test_001",
                "forwarded_count": "0",
                "action": "notify",
                "message_type": "event",
                "reason": "A trusted group admin sent a time-sensitive update.",
                "confidence": 0.85,
                "evidence_message_ids": "none",
            }
        ]
    )

    inner_ocr = FakeOCRClient(OCRResult("Poster", 0.8, "poster_promo", False, None))
    ocr_client = CachingOCRClient(inner_ocr)
    asr_client = CachingASRClient(FakeASRClient())
    dataset_dir = fixtures_dir / "dataset_valid"

    main._route_bundle(bundle, dataset_dir, ocr_client, asr_client)
    main._calibrate(bundle, dataset_dir, ocr_client, asr_client)

    assert len(inner_ocr.calls) == 1
