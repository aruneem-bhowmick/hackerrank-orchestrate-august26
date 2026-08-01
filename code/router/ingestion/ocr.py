"""Extracts text and a coarse category from image messages via Anthropic's vision API.

ADR-001/ADR-007 (SPEC.md §5): OCR is a single call per image to Anthropic's
vision-capable Messages API, using forced tool-use so the response is
structured JSON rather than free-text to parse. One call returns both the
extracted text and a coarse category classification, so a second paid call
is never needed just to categorize an image already being read for text.
"""

import base64
import math
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import anthropic

from router.errors import OCRClientError
from router.ingestion.categories import IMAGE_CATEGORIES

_DEFAULT_OCR_MODEL = "claude-sonnet-5"
_DEFAULT_MAX_TOKENS = 1024
_DEFAULT_IMAGE_MEDIA_TYPE = "image/jpeg"

_OCR_TOOL_NAME = "submit_image_analysis"

_OCR_INSTRUCTION = (
    "Analyze this image for a WhatsApp message routing system. Extract any "
    "readable text (poster copy, screenshot text, document text, captions "
    "baked into the image). Classify the image into exactly one coarse "
    "category. Report your confidence in the extraction. Use the "
    "submit_image_analysis tool to report your findings."
)

_NO_READABLE_TEXT_REASON = "the vision model found no readable text in the image"


def _ocr_tool_schema() -> dict:
    """Build the forced tool-use schema, sourcing the category enum from categories.py."""
    return {
        "name": _OCR_TOOL_NAME,
        "description": "Report the text extracted from an image and its coarse category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "has_readable_text": {
                    "type": "boolean",
                    "description": "Whether the image contains any readable text.",
                },
                "extracted_text": {
                    "type": "string",
                    "description": "Every piece of readable text in the image, or an empty string.",
                },
                "category": {
                    "type": "string",
                    "enum": sorted(IMAGE_CATEGORIES),
                    "description": "The single best-fit coarse category for this image.",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in the extraction, from 0 to 1.",
                },
            },
            "required": ["has_readable_text", "extracted_text", "category", "confidence"],
        },
    }


@dataclass(frozen=True)
class OCRResult:
    """One OCR call's outcome.

    category/confidence are always present even when failure=True — a
    model may report "no readable text" while still offering a category
    guess and a low confidence, and both remain useful signal, not noise
    to discard.
    """

    text: str
    confidence: float
    category: str | None
    failure: bool
    failure_reason: str | None


class OCRClient(Protocol):
    """The OCR boundary every caller in this package depends on, never a concrete client."""

    def extract(self, image_path: Path) -> OCRResult:
        """Run OCR (and category classification) on one image file.

        Raises OCRClientError on any failure to obtain a response at all
        (missing key, network/API error, unreadable file, unparseable
        response) — never returns a fabricated OCRResult in that case.
        """
        ...


class AnthropicOCRClient:
    """OCRClient backed by Anthropic's vision-capable Messages API."""

    def __init__(self, api_key: str, model: str = _DEFAULT_OCR_MODEL) -> None:
        """Build a client bound to one Anthropic API key and model."""
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def extract(self, image_path: Path) -> OCRResult:
        """Call the Anthropic Messages API once for image_path and parse the tool result."""
        try:
            image_data = image_path.read_bytes()
        except OSError as exc:
            raise OCRClientError(f"Could not read image file '{image_path}': {exc}") from exc

        media_type = mimetypes.guess_type(str(image_path))[0] or _DEFAULT_IMAGE_MEDIA_TYPE
        encoded = base64.standard_b64encode(image_data).decode("ascii")

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_DEFAULT_MAX_TOKENS,
                tools=[_ocr_tool_schema()],
                tool_choice={"type": "tool", "name": _OCR_TOOL_NAME},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": encoded,
                                },
                            },
                            {"type": "text", "text": _OCR_INSTRUCTION},
                        ],
                    }
                ],
            )
        except anthropic.APIError as exc:
            raise OCRClientError(
                f"Anthropic OCR request failed for '{image_path.name}': {exc}"
            ) from exc

        return _ocr_result_from_response(response, image_path)


class _UnconfiguredOCRClient:
    """OCRClient stand-in used when ANTHROPIC_API_KEY is not set.

    Raises OCRClientError on first use rather than at import/construction
    time, so a key-less run still completes end to end — every image
    message lands in the media-failure fallback path instead of halting
    the whole pipeline.
    """

    def extract(self, image_path: Path) -> OCRResult:
        """Always raise: no OCR is possible without a configured API key."""
        raise OCRClientError("ANTHROPIC_API_KEY is not set; cannot run OCR.")


def build_ocr_client() -> OCRClient:
    """Return an AnthropicOCRClient built from ANTHROPIC_API_KEY, or an unconfigured fallback."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return _UnconfiguredOCRClient()
    return AnthropicOCRClient(api_key=api_key)


def _find_tool_use_block(response: object, tool_name: str) -> object | None:
    """Return the first content block of response matching tool_name, or None."""
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
            return block
    return None


def _ocr_result_from_response(response: object, image_path: Path) -> OCRResult:
    """Parse an Anthropic Messages response into an OCRResult, or raise OCRClientError."""
    tool_use = _find_tool_use_block(response, _OCR_TOOL_NAME)
    if tool_use is None:
        raise OCRClientError(
            f"Anthropic OCR response for '{image_path.name}' did not include "
            f"the expected '{_OCR_TOOL_NAME}' tool result"
        )

    payload = getattr(tool_use, "input", None)
    if not isinstance(payload, dict):
        raise OCRClientError(
            f"Anthropic OCR response for '{image_path.name}' had a malformed tool result"
        )

    try:
        has_readable_text = payload["has_readable_text"]
        text = payload["extracted_text"]
        category = payload.get("category")
        confidence = payload["confidence"]
    except KeyError as exc:
        raise OCRClientError(
            f"Anthropic OCR response for '{image_path.name}' had an incomplete tool result: {exc}"
        ) from exc

    if (
        not isinstance(has_readable_text, bool)
        or not isinstance(text, str)
        or (category is not None and not isinstance(category, str))
        or isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(float(confidence))
    ):
        raise OCRClientError(
            f"Anthropic OCR response for '{image_path.name}' had a malformed tool result"
        )

    confidence = max(0.0, min(1.0, float(confidence)))

    failure = not has_readable_text or not text.strip()
    return OCRResult(
        text=text,
        confidence=confidence,
        category=category,
        failure=failure,
        failure_reason=_NO_READABLE_TEXT_REASON if failure else None,
    )
