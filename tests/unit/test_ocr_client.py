"""Unit tests for the structured Anthropic OCR boundary."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from router.errors import OCRClientError
from router.ingestion import ocr


def _response(payload: object) -> SimpleNamespace:
    """Build the minimal Anthropic response shape consumed by the parser."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="submit_image_analysis", input=payload)]
    )


def test_ocr_tool_schema_uses_the_fixed_image_category_taxonomy():
    """The API schema accepts only the shared, deterministic category set."""
    schema = ocr._ocr_tool_schema()
    category = schema["input_schema"]["properties"]["category"]

    assert category["enum"] == sorted(ocr.IMAGE_CATEGORIES)
    assert schema["input_schema"]["required"] == [
        "has_readable_text",
        "extracted_text",
        "category",
        "confidence",
    ]


def test_ocr_response_parser_returns_text_category_and_clamped_confidence(tmp_path):
    """A valid tool response produces a successful normalized OCR result."""
    result = ocr._ocr_result_from_response(
        _response(
            {
                "has_readable_text": True,
                "extracted_text": "Flash sale today",
                "category": "poster_promo",
                "confidence": 2.0,
            }
        ),
        tmp_path / "poster.jpg",
    )

    assert result.text == "Flash sale today"
    assert result.category == "poster_promo"
    assert result.confidence == 1.0
    assert result.failure is False
    assert result.failure_reason is None


def test_ocr_response_parser_marks_no_readable_text_as_a_non_crashing_failure(tmp_path):
    """A normal no-text result remains structured instead of raising an API error."""
    result = ocr._ocr_result_from_response(
        _response(
            {
                "has_readable_text": False,
                "extracted_text": "",
                "category": "meme",
                "confidence": 0.19,
            }
        ),
        tmp_path / "meme.jpg",
    )

    assert result.failure is True
    assert result.failure_reason == "the vision model found no readable text in the image"
    assert result.category == "meme"


@pytest.mark.parametrize(
    "response",
    [SimpleNamespace(content=[]), _response({"has_readable_text": True})],
)
def test_ocr_response_parser_rejects_missing_or_incomplete_tool_results(tmp_path, response):
    """Malformed model responses are explicit client errors, never guessed text."""
    with pytest.raises(OCRClientError, match="tool result"):
        ocr._ocr_result_from_response(response, tmp_path / "bad.jpg")


def test_anthropic_client_builds_a_forced_tool_request(monkeypatch, tmp_path):
    """The concrete client sends image bytes and requires the structured response tool."""
    image_path = tmp_path / "poster.jpg"
    image_path.write_bytes(b"image-bytes")
    recorded: dict[str, object] = {}

    class Messages:
        """Minimal recording endpoint used to inspect a request without network I/O."""

        def create(self, **kwargs):
            """Record the payload and return a successful tool-use response."""
            recorded.update(kwargs)
            return _response(
                {
                    "has_readable_text": True,
                    "extracted_text": "Offer",
                    "category": "poster_promo",
                    "confidence": 0.8,
                }
            )

    class Client:
        """Replacement Anthropic client exposing the expected messages endpoint."""

        def __init__(self, api_key):
            """Retain the supplied key only for the assertion below."""
            recorded["api_key"] = api_key
            self.messages = Messages()

    monkeypatch.setattr(ocr.anthropic, "Anthropic", Client)
    result = ocr.AnthropicOCRClient("test-key").extract(image_path)

    assert result.text == "Offer"
    assert recorded["api_key"] == "test-key"
    assert recorded["tool_choice"] == {"type": "tool", "name": "submit_image_analysis"}
    assert recorded["messages"][0]["content"][0]["source"]["data"] == "aW1hZ2UtYnl0ZXM="


def test_build_ocr_client_without_a_key_defers_failure_to_extraction(monkeypatch, tmp_path):
    """A key-less command can start; only the specific image extraction fails."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(OCRClientError, match="ANTHROPIC_API_KEY"):
        ocr.build_ocr_client().extract(Path(tmp_path / "missing.jpg"))
