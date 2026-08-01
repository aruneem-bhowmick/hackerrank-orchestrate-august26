"""Fake OCR/ASR clients shared across the media ingestion test suite.

Every test that needs an OCRClient/ASRClient uses one of these instead of
a real Anthropic/OpenAI client — no test in this suite makes a live
network call.
"""

from pathlib import Path

from router.errors import ASRClientError, OCRClientError
from router.ingestion.asr import ASRResult
from router.ingestion.ocr import OCRResult


class FakeOCRClient:
    """OCRClient test double returning a scripted result or raising a scripted error.

    Records every image_path it is called with, so tests can assert both
    the returned/raised outcome and how many times (and with what path)
    the client was actually invoked.
    """

    def __init__(self, result: OCRResult | None = None, error: OCRClientError | None = None):
        """Script this fake to return result, or raise error, on every extract() call."""
        self.result = result
        self.error = error
        self.calls: list[Path] = []

    def extract(self, image_path: Path) -> OCRResult:
        """Record the call, then return the scripted result or raise the scripted error."""
        self.calls.append(image_path)
        if self.error is not None:
            raise self.error
        return self.result


class FakeASRClient:
    """ASRClient test double returning a scripted result or raising a scripted error.

    Records every audio_path it is called with, mirroring FakeOCRClient.
    """

    def __init__(self, result: ASRResult | None = None, error: ASRClientError | None = None):
        """Script this fake to return result, or raise error, on every transcribe() call."""
        self.result = result
        self.error = error
        self.calls: list[Path] = []

    def transcribe(self, audio_path: Path) -> ASRResult:
        """Record the call, then return the scripted result or raise the scripted error."""
        self.calls.append(audio_path)
        if self.error is not None:
            raise self.error
        return self.result
