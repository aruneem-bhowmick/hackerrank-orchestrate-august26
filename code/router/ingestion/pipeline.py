"""Normalizes one message at a time to the NormalizedMessage contract, per SPEC.md §1.2."""

from pathlib import Path
from typing import Mapping

from router.dataset.loader import DatasetBundle
from router.errors import ASRClientError, OCRClientError
from router.ingestion.asr import ASRClient, ASRResult
from router.ingestion.categories import VOICE_NOTE_CATEGORY, validate_image_category
from router.ingestion.media import lookup_media_file_path
from router.ingestion.message import NormalizedMessage
from router.ingestion.ocr import OCRClient, OCRResult

_FAILURE_CONFIDENCE_CAP = 0.2
"""The ceiling media_confidence is clamped to on any REQ-P2-04 fallback
path — low enough to signal "do not trust this," non-zero so a client that
did offer some confidence before failing is not flattened to an
indistinguishable zero."""


def normalize_message(
    message: Mapping[str, object],
    bundle: DatasetBundle,
    dataset_dir: Path,
    ocr_client: OCRClient,
    asr_client: ASRClient,
) -> NormalizedMessage:
    """Normalize one messages.csv row (as a dict/record) to a NormalizedMessage.

    Dispatches on media_type: "" passes message_text through unchanged;
    "image" runs OCR and combines the result with the caption; "voice"
    runs ASR and returns the transcript alone (voice messages carry no
    native caption) through the exact same NormalizedMessage shape — no
    forked downstream logic. Never raises for a well-formed row regardless
    of OCR/ASR outcome — see the REQ-P2-04 fallback contract implemented
    in _normalize_image_message/_normalize_voice_message.
    """
    media_type = _string(message, "media_type")
    if media_type == "image":
        return _normalize_image_message(message, bundle, dataset_dir, ocr_client)
    if media_type == "voice":
        return _normalize_voice_message(message, bundle, dataset_dir, asr_client)
    return _normalize_text_message(message)


def _string(message: Mapping[str, object], field: str) -> str:
    """Return a string field from a message record, treating nulls/missing as blank."""
    value = message.get(field, "")
    return value if isinstance(value, str) else ""


def _build_normalized_message(
    message: Mapping[str, object],
    text: str,
    confidence: float,
    failure: bool,
    category: str | None,
    failure_reason: str | None,
) -> NormalizedMessage:
    """Assemble a NormalizedMessage from a message record plus the ingestion outcome fields.

    The single constructor every branch below funnels through, so the
    seven passthrough fields (message_id, user_id, ...) are copied from
    message in exactly one place.
    """
    return NormalizedMessage(
        message_id=_string(message, "message_id"),
        user_id=_string(message, "user_id"),
        conversation_type=_string(message, "conversation_type"),
        group_id=_string(message, "group_id"),
        business_id=_string(message, "business_id"),
        sender_user_id=_string(message, "sender_user_id"),
        created_at=_string(message, "created_at"),
        media_type=_string(message, "media_type"),
        normalized_text=text,
        media_confidence=confidence,
        media_failure=failure,
        media_category=category,
        media_failure_reason=failure_reason,
    )


def _normalize_text_message(message: Mapping[str, object]) -> NormalizedMessage:
    """Build a NormalizedMessage for a text (or blank-media_type) message."""
    return _build_normalized_message(
        message,
        text=_string(message, "message_text"),
        confidence=1.0,
        failure=False,
        category=None,
        failure_reason=None,
    )


def _fallback_normalized_message(
    message: Mapping[str, object], text: str, reason: str, category: str | None
) -> NormalizedMessage:
    """Build the shared "could not ingest" NormalizedMessage shape (REQ-P2-04).

    Used whenever media cannot be ingested at all — a missing media_id, a
    missing images.csv/voice_notes.csv record, or (via each modality's own
    branch) a client-reported or client-raised OCR/ASR failure.
    """
    return _build_normalized_message(
        message, text=text, confidence=0.0, failure=True, category=category, failure_reason=reason
    )


def _normalize_image_message(
    message: Mapping[str, object], bundle: DatasetBundle, dataset_dir: Path, ocr_client: OCRClient
) -> NormalizedMessage:
    """Build a NormalizedMessage for an image message, combining caption and OCR text.

    Per ADR-007: normalized_text is the caption and the OCR transcript
    concatenated when both are present, OCR alone when there is no
    caption, and the caption alone when OCR fails or finds nothing — OCR
    failure never blanks out a caption that was already there.
    """
    media_id = _string(message, "media_id")
    caption = _string(message, "message_text")

    image_path = (
        lookup_media_file_path(media_id, bundle.images, "image_id", dataset_dir) if media_id else None
    )
    if image_path is None:
        reason = (
            f"no images.csv record found for media_id '{media_id}'"
            if media_id
            else "image message has no media_id"
        )
        return _fallback_normalized_message(message, text=caption, reason=reason, category=None)

    try:
        result = ocr_client.extract(image_path)
    except OCRClientError as exc:
        result = OCRResult(text="", confidence=0.0, category=None, failure=True, failure_reason=str(exc))

    if result.failure or not result.text.strip():
        return _build_normalized_message(
            message,
            text=caption,
            confidence=min(result.confidence, _FAILURE_CONFIDENCE_CAP),
            failure=True,
            category=validate_image_category(result.category),
            failure_reason=result.failure_reason or "OCR produced no readable text",
        )

    extracted = result.text.strip()
    text = f"{caption}\n{extracted}".strip() if caption else extracted
    return _build_normalized_message(
        message,
        text=text,
        confidence=result.confidence,
        failure=False,
        category=validate_image_category(result.category),
        failure_reason=None,
    )


def _normalize_voice_message(
    message: Mapping[str, object], bundle: DatasetBundle, dataset_dir: Path, asr_client: ASRClient
) -> NormalizedMessage:
    """Build a NormalizedMessage for a voice message, via its ASR transcript alone.

    Voice messages carry no native caption (message_text is always blank
    per the input schema), so normalized_text is the transcript on
    success or "" on any failure — there is nothing else to fall back to.
    media_category is always VOICE_NOTE_CATEGORY, success or failure —
    unlike an image, a voice message's category is never unknown, only
    its transcript is.
    """
    media_id = _string(message, "media_id")

    audio_path = (
        lookup_media_file_path(media_id, bundle.voice_notes, "voice_note_id", dataset_dir)
        if media_id
        else None
    )
    if audio_path is None:
        reason = (
            f"no voice_notes.csv record found for media_id '{media_id}'"
            if media_id
            else "voice message has no media_id"
        )
        return _fallback_normalized_message(
            message, text="", reason=reason, category=VOICE_NOTE_CATEGORY
        )

    try:
        result = asr_client.transcribe(audio_path)
    except ASRClientError as exc:
        result = ASRResult(text="", confidence=0.0, failure=True, failure_reason=str(exc))

    if result.failure or not result.text.strip():
        return _build_normalized_message(
            message,
            text="",
            confidence=min(result.confidence, _FAILURE_CONFIDENCE_CAP),
            failure=True,
            category=VOICE_NOTE_CATEGORY,
            failure_reason=result.failure_reason or "ASR produced no usable transcript",
        )

    return _build_normalized_message(
        message,
        text=result.text.strip(),
        confidence=result.confidence,
        failure=False,
        category=VOICE_NOTE_CATEGORY,
        failure_reason=None,
    )
