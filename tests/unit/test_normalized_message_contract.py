"""Unit tests for the NormalizedMessage contract."""

import dataclasses

import pytest

from router.ingestion.message import NormalizedMessage

_FIELDS = (
    "message_id",
    "user_id",
    "conversation_type",
    "group_id",
    "business_id",
    "sender_user_id",
    "created_at",
    "media_type",
    "normalized_text",
    "media_confidence",
    "media_failure",
    "media_category",
    "media_failure_reason",
)


def _build(**overrides) -> NormalizedMessage:
    """Construct a NormalizedMessage with sensible text-message defaults."""
    values = {
        "message_id": "msg_1",
        "user_id": "u_1",
        "conversation_type": "personal",
        "group_id": "",
        "business_id": "",
        "sender_user_id": "u_2",
        "created_at": "2026-08-01 09:00",
        "media_type": "",
        "normalized_text": "Hello there.",
        "media_confidence": 1.0,
        "media_failure": False,
        "media_category": None,
        "media_failure_reason": None,
    }
    values.update(overrides)
    return NormalizedMessage(**values)


def test_every_contract_field_is_set_and_readable():
    """Every §1.2 field, including the media_failure_reason extension, round-trips."""
    message = _build(
        media_type="image",
        media_confidence=0.8,
        media_failure=False,
        media_category="poster_promo",
        media_failure_reason=None,
    )
    for field in _FIELDS:
        assert hasattr(message, field)
    assert message.media_category == "poster_promo"
    assert message.media_failure_reason is None


def test_media_failure_reason_present_when_media_failure_true():
    """A failed message carries a non-empty, specific media_failure_reason."""
    message = _build(
        media_type="voice",
        normalized_text="",
        media_confidence=0.0,
        media_failure=True,
        media_category="voice_note",
        media_failure_reason="no speech segments detected in the audio",
    )
    assert message.media_failure is True
    assert message.media_failure_reason
    assert message.media_failure_reason.strip() != ""


def test_text_message_defaults_match_the_no_media_shape():
    """A plain text message's shape: confidence 1.0, no failure, no category."""
    message = _build()
    assert message.media_type == ""
    assert message.media_confidence == 1.0
    assert message.media_failure is False
    assert message.media_category is None
    assert message.media_failure_reason is None


def test_normalized_message_is_frozen():
    """NormalizedMessage instances cannot be mutated after construction."""
    message = _build()
    with pytest.raises(dataclasses.FrozenInstanceError):
        message.normalized_text = "changed"


def test_missing_required_field_raises_type_error():
    """Every field is required — a missing one is a construction-time error, not a silent default."""
    with pytest.raises(TypeError):
        NormalizedMessage(message_id="msg_1")
