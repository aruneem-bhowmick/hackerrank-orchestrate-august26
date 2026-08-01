"""Selects message_type from the fixed allowed-value list.

Priority order: a safety-forced label first (REQ-P1-04's mute is not
undone here, but its risk_type is not blindly copied into message_type
either — SPEC.md ADR-006 documents that risk_type is an intermediate
signal, not a guaranteed final label), then a personalization-driven
business-mute label, then deterministic content classification.
"""

import re
from collections.abc import Mapping

from router.decision.content_signals import detect_content_urgency
from router.errors import DecisionFusionError
from router.ingestion.message import NormalizedMessage
from router.safety.thresholds import FORWARD_CHAIN_COUNT_THRESHOLD
from router.safety.verdict import SafetyVerdict

ALLOWED_MESSAGE_TYPES: frozenset[str] = frozenset(
    {
        "personal",
        "urgent",
        "event",
        "payment",
        "business_update",
        "promotion",
        "greeting",
        "forward",
        "spam",
        "scam",
        "unknown",
    }
)
"""The fixed allowed-value list from problem_statement.md — never extended
or invented from; see validate_message_type."""

_GREETING_PATTERN = re.compile(
    r"good morning|good evening|stay positive|keep smiling|"
    r"share blessings|forwarding because it felt nice|"
    r"sending good vibes|hope today is peaceful",
    re.IGNORECASE,
)
"""Blessing/well-wish language only — "no need to respond" was dropped after
calibration showed it also fires on ordinary non-greeting group notices that
simply do not require acknowledgment (e.g. a form/circular announcement)."""

_EVENT_PATTERN = re.compile(
    r"\bcircular\b|\bschedule\b|\btiming\b|\bform\b|\bappointment\b|"
    r"\bbooking\b|cultural night|consent note|\bregistration\b|"
    r"prescription|claim|leaving \d+ mins? early",
    re.IGNORECASE,
)
"""Schedule/logistics language. "pickup" and "delivery-code" were dropped
after calibration showed both fire on item-for-sale/order-tracking content
(message_type promotion/business_update), not on scheduled events."""

_PAYMENT_PATTERN = re.compile(
    r"\binvoice\b|\bbill\b|\bdue\b|\bemi\b|\brefund\b|amount debited|"
    r"amount credited|payment reminder|subscription renewal",
    re.IGNORECASE,
)

_PROMOTION_PATTERN = re.compile(
    r"\d+%\s*off|\bsale\b|\boffer\b|\bpromo\b|\bdiscount\b|\bselling\b|"
    r"shopping offer|unsubscribe|reply stop",
    re.IGNORECASE,
)

_IMAGE_PICKUP_PATTERN = re.compile(r"\bpickup\b", re.IGNORECASE)
""""pickup" alone is ambiguous — dataset/sample_messages.csv uses it both for
a casual personal carpool chat (sample_msg_006, text-only) and for an
item-for-sale collection arrangement (sample_msg_044/045/047, all image
captions). Restricting this signal to image messages resolves that
ambiguity without treating the bare word as reliable on its own."""


def select_message_type(
    verdict: SafetyVerdict,
    action: str,
    message: NormalizedMessage,
    signals: Mapping[str, object],
    business: Mapping[str, object] | None,
    forwarded_count: int,
) -> str:
    """Deterministically select one member of ALLOWED_MESSAGE_TYPES.

    Priority order: a safety-forced label (is_blocked scam/spam) first,
    then a personalization-driven business-mute label, then content-based
    classification of message.normalized_text. Always returns a member of
    ALLOWED_MESSAGE_TYPES — never raises for well-formed input, and never
    invents a value outside that set.
    """
    if verdict.is_blocked and verdict.risk_type == "scam":
        return validate_message_type("scam")

    if verdict.is_blocked and verdict.risk_type == "spam":
        if forwarded_count >= FORWARD_CHAIN_COUNT_THRESHOLD:
            return validate_message_type("forward")
        return validate_message_type("spam")

    if action == "mute" and message.conversation_type == "business":
        if business is not None and str(business.get("verified", "")).strip() == "0":
            return validate_message_type("spam")
        return validate_message_type("promotion")

    return validate_message_type(_classify_content(message, signals))


def validate_message_type(raw: str) -> str:
    """Return raw if it is a member of ALLOWED_MESSAGE_TYPES, else raise
    DecisionFusionError.

    A defense against a future code path returning an off-taxonomy value —
    mirrors router.ingestion.categories.validate_image_category's role for
    P2, adapted to raise rather than fall back, since every message_type
    branch in this module is a fixed literal the module itself controls
    (unlike an external model's free-text category output).
    """
    if raw not in ALLOWED_MESSAGE_TYPES:
        raise DecisionFusionError(f"'{raw}' is not a member of ALLOWED_MESSAGE_TYPES.")
    return raw


def _classify_content(message: NormalizedMessage, signals: Mapping[str, object]) -> str:
    """Classify message.normalized_text into a coarse content-based message_type.

    A direct mention or a plain request for a response ("can you call?")
    is not, by itself, treated as "urgent" — calibration against
    dataset/sample_messages.csv showed a personal direct ask keeps
    message_type "personal" even when it resolves to action "notify";
    "urgent" is reserved for explicit deadline/escalation language (see
    router.decision.content_signals.detect_content_urgency).
    """
    text = message.normalized_text or ""

    if _GREETING_PATTERN.search(text):
        return "greeting"
    if _EVENT_PATTERN.search(text):
        return "event"
    if detect_content_urgency(text):
        return "urgent"
    if _PAYMENT_PATTERN.search(text):
        return "payment"
    if _PROMOTION_PATTERN.search(text):
        return "promotion"
    if message.media_type == "image" and _IMAGE_PICKUP_PATTERN.search(text):
        return "promotion"

    if message.conversation_type == "business":
        return "business_update"
    if message.conversation_type == "personal" and int(signals["source_history_count"]) == 0:
        return "unknown"
    return "personal"


__all__ = ["ALLOWED_MESSAGE_TYPES", "select_message_type", "validate_message_type"]
