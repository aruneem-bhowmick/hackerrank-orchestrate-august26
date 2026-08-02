"""Unit tests for media-result caching decorators."""

from pathlib import Path

import pandas as pd
import pytest

from router.errors import ASRClientError, OCRClientError
from router.ingestion.asr import ASRResult
from router.ingestion.cache import CachingASRClient, CachingOCRClient
from router.ingestion.ocr import OCRResult
from router.ingestion.pipeline import run_media_ingestion

from ingestion_fakes import FakeASRClient, FakeOCRClient, make_message


def test_ocr_cache_reuses_results_for_the_same_media_path(tmp_path):
    """Repeated image references invoke the wrapped OCR client exactly once."""
    inner = FakeOCRClient(OCRResult("Poster", 0.8, "poster_promo", False, None))
    cached = CachingOCRClient(inner)
    image_path = Path(tmp_path / "poster.jpg")

    assert cached.extract(image_path) == cached.extract(image_path)
    assert inner.calls == [image_path]


def test_asr_cache_reuses_results_for_the_same_media_path(tmp_path):
    """Repeated voice references invoke the wrapped ASR client exactly once."""
    inner = FakeASRClient(ASRResult("Call me", 0.8, False, None))
    cached = CachingASRClient(inner)
    audio_path = Path(tmp_path / "voice.mp3")

    assert cached.transcribe(audio_path) == cached.transcribe(audio_path)
    assert inner.calls == [audio_path]


def test_ocr_cache_does_not_merge_different_media_paths(tmp_path):
    """Distinct media IDs remain independent cache entries even with identical scripted output."""
    inner = FakeOCRClient(OCRResult("Poster", 0.8, "poster_promo", False, None))
    cached = CachingOCRClient(inner)

    cached.extract(tmp_path / "one.jpg")
    cached.extract(tmp_path / "two.jpg")

    assert len(inner.calls) == 2


def test_ocr_cache_re_raises_a_cached_failure_without_retrying(tmp_path):
    """A deterministic client error does not incur another failed paid request."""
    inner = FakeOCRClient(error=OCRClientError("request failed"))
    cached = CachingOCRClient(inner)
    image_path = tmp_path / "bad.jpg"

    with pytest.raises(OCRClientError, match="request failed"):
        cached.extract(image_path)
    with pytest.raises(OCRClientError, match="request failed"):
        cached.extract(image_path)

    assert inner.calls == [image_path]


def test_asr_cache_re_raises_a_cached_failure_without_retrying(tmp_path):
    """Voice transcription failures obey the same one-call cache discipline."""
    inner = FakeASRClient(error=ASRClientError("request failed"))
    cached = CachingASRClient(inner)
    audio_path = tmp_path / "bad.mp3"

    with pytest.raises(ASRClientError, match="request failed"):
        cached.transcribe(audio_path)
    with pytest.raises(ASRClientError, match="request failed"):
        cached.transcribe(audio_path)

    assert inner.calls == [audio_path]


def test_run_media_ingestion_reuses_a_caller_supplied_caching_client(load_fixture_bundle, fixtures_dir):
    """A CachingOCRClient passed to two separate batch calls is not re-wrapped."""
    bundle = load_fixture_bundle("dataset_valid")
    image_message = make_message(message_id="img_message", media_type="image", media_id="img_test_001")
    bundle.messages = pd.DataFrame([image_message], columns=list(image_message))

    inner = FakeOCRClient(OCRResult("Poster", 0.8, "poster_promo", False, None))
    shared_ocr_client = CachingOCRClient(inner)

    run_media_ingestion(bundle, fixtures_dir / "dataset_valid", shared_ocr_client, FakeASRClient())
    run_media_ingestion(bundle, fixtures_dir / "dataset_valid", shared_ocr_client, FakeASRClient())

    assert len(inner.calls) == 1
