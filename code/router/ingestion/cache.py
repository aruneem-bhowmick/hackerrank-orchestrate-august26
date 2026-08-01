"""Wraps the OCR/ASR client boundary so a media_id is never ingested twice in one run."""

from pathlib import Path

from router.errors import ASRClientError, OCRClientError
from router.ingestion.asr import ASRClient, ASRResult
from router.ingestion.ocr import OCRClient, OCRResult


class CachingOCRClient:
    """Wraps an OCRClient, caching results (and failures) by resolved image path.

    A media_id referenced by more than one message resolves to the same
    file path every time (via lookup_media_file_path), so keying on the
    path is equivalent to keying on media_id without requiring extract()'s
    signature to carry an extra parameter. Cache scope is exactly one
    instance's lifetime — a fresh cache per batch run, never shared across
    instances.
    """

    def __init__(self, inner: OCRClient) -> None:
        """Wrap inner, starting from an empty cache."""
        self._inner = inner
        self._cache: dict[str, OCRResult | OCRClientError] = {}

    def extract(self, image_path: Path) -> OCRResult:
        """Return a cached result/re-raise a cached failure, or delegate and cache the outcome."""
        key = str(image_path)
        if key in self._cache:
            cached = self._cache[key]
            if isinstance(cached, OCRClientError):
                raise cached
            return cached

        try:
            result = self._inner.extract(image_path)
        except OCRClientError as exc:
            self._cache[key] = exc
            raise
        self._cache[key] = result
        return result


class CachingASRClient:
    """As CachingOCRClient, for ASRClient.transcribe."""

    def __init__(self, inner: ASRClient) -> None:
        """Wrap inner, starting from an empty cache."""
        self._inner = inner
        self._cache: dict[str, ASRResult | ASRClientError] = {}

    def transcribe(self, audio_path: Path) -> ASRResult:
        """Return a cached result/re-raise a cached failure, or delegate and cache the outcome."""
        key = str(audio_path)
        if key in self._cache:
            cached = self._cache[key]
            if isinstance(cached, ASRClientError):
                raise cached
            return cached

        try:
            result = self._inner.transcribe(audio_path)
        except ASRClientError as exc:
            self._cache[key] = exc
            raise
        self._cache[key] = result
        return result
