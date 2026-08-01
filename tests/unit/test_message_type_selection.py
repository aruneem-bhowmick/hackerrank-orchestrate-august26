"""Unit tests for router.decision.message_type.select_message_type."""

import pytest
from decision_signals import make_signals, make_verdict
from message_type_samples import make_business, make_normalized_message

from router.decision.message_type import (
    ALLOWED_MESSAGE_TYPES,
    select_message_type,
    validate_message_type,
)
from router.errors import DecisionFusionError


def test_blocked_scam_selects_scam():
    """A safety-forced scam verdict always selects message_type scam."""
    verdict = make_verdict(is_blocked=True, risk_type="scam", risk_confidence=0.9)
    message = make_normalized_message(normalized_text="anything")

    result = select_message_type(verdict, "mute", message, make_signals(), None, 0)

    assert result == "scam"


def test_blocked_spam_with_high_forwarded_count_selects_forward():
    """A blocked spam verdict with a mass-forward-level count selects forward, not spam."""
    verdict = make_verdict(is_blocked=True, risk_type="spam", risk_confidence=0.6)
    message = make_normalized_message(normalized_text="fwd as received, drink warm water")

    result = select_message_type(verdict, "mute", message, make_signals(), None, 11)

    assert result == "forward"


def test_blocked_spam_with_low_forwarded_count_selects_spam():
    """A blocked spam verdict without a high forward count selects spam."""
    verdict = make_verdict(is_blocked=True, risk_type="spam", risk_confidence=0.6)
    message = make_normalized_message(normalized_text="huge sale today")

    result = select_message_type(verdict, "mute", message, make_signals(), None, 1)

    assert result == "spam"


def test_personalization_mute_of_unverified_business_selects_spam():
    """A personalization-driven business mute selects spam when the sender is unverified."""
    verdict = make_verdict()
    message = make_normalized_message(conversation_type="business", normalized_text="reminder")
    business = make_business(verified="0")

    result = select_message_type(verdict, "mute", message, make_signals(), business, 0)

    assert result == "spam"


def test_personalization_mute_of_verified_business_selects_promotion():
    """A personalization-driven business mute selects promotion when the sender is verified."""
    verdict = make_verdict()
    message = make_normalized_message(conversation_type="business", normalized_text="50% off")
    business = make_business(verified="1")

    result = select_message_type(verdict, "mute", message, make_signals(), business, 3)

    assert result == "promotion"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Good morning everyone, stay positive and keep smiling", "greeting"),
        ("Cultural night form is open, add your flat no", "event"),
        ("Retry count crossed the alert threshold, escalation starts asap", "urgent"),
        ("Your invoice is due, please pay the EMI amount", "payment"),
        ("Flat 50% off, hurry the offer expires soon", "promotion"),
    ],
)
def test_content_classification_buckets(text: str, expected: str):
    """Each content keyword bucket selects its matching message_type."""
    verdict = make_verdict()
    message = make_normalized_message(conversation_type="group", normalized_text=text)

    result = select_message_type(verdict, "notify", message, make_signals(), None, 0)

    assert result == expected


def test_personal_conversation_with_no_history_selects_unknown():
    """A first-contact personal message with no clear content pattern is unknown."""
    verdict = make_verdict()
    message = make_normalized_message(conversation_type="personal", normalized_text="Are you free Saturday?")

    result = select_message_type(verdict, "digest", message, make_signals(source_history_count=0), None, 0)

    assert result == "unknown"


def test_personal_conversation_with_history_selects_personal():
    """A familiar sender's casual message selects personal, not unknown."""
    verdict = make_verdict()
    message = make_normalized_message(conversation_type="personal", normalized_text="Reached home, talk tomorrow")

    result = select_message_type(verdict, "digest", message, make_signals(source_history_count=5), None, 0)

    assert result == "personal"


def test_business_conversation_default_selects_business_update():
    """A business message matching no other content pattern defaults to business_update."""
    verdict = make_verdict()
    message = make_normalized_message(conversation_type="business", normalized_text="Thank you for choosing us, please give feedback")

    result = select_message_type(verdict, "digest", message, make_signals(), make_business(), 0)

    assert result == "business_update"


def test_validate_message_type_rejects_off_taxonomy_value():
    """validate_message_type raises rather than silently accepting an invented category."""
    with pytest.raises(DecisionFusionError, match="not a member"):
        validate_message_type("newsletter")


@pytest.mark.parametrize("conversation_type", ["personal", "group", "business"])
def test_selection_always_returns_an_allowed_value(conversation_type: str):
    """Property check: every branch's output is a member of ALLOWED_MESSAGE_TYPES."""
    verdict = make_verdict()
    message = make_normalized_message(conversation_type=conversation_type, normalized_text="hello there")

    result = select_message_type(verdict, "digest", message, make_signals(), make_business(), 0)

    assert result in ALLOWED_MESSAGE_TYPES
