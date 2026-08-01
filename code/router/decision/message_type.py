"""Selects message_type from the fixed allowed-value list.

Priority order: a safety-forced label first (REQ-P1-04's mute is not
undone here, but its risk_type is not blindly copied into message_type
either — SPEC.md ADR-006 documents that risk_type is an intermediate
signal, not a guaranteed final label), then a personalization-driven
business-mute label, then deterministic content classification.
"""

import re
from collections.abc import Mapping

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
    r"share blessings|no need to (?:respond|reply)|forwarding because it felt nice|"
    r"sending good vibes|hope today is peaceful",
    re.IGNORECASE,
)

_EVENT_PATTERN = re.compile(
    r"\bcircular\b|\bschedule\b|\btiming\b|\bpickup\b|\bform\b|\bappointment\b|"
    r"\bbooking\b|cultural night|consent note|\bregistration\b|"
    r"prescription|claim|delivery-code|leaving \d+ mins? early",
    re.IGNORECASE,
)

_URGENT_PATTERN = re.compile(
    r"\basap\b|\burgent\b|immediately|before (?:eod|midnight)|"
    r"\bescalat\w*|expire[sd]? today|within \d+ (?:minutes?|hours?)|"
    r"in \d+ mins?|quick heads-up|retry count crossed",
    re.IGNORECASE,
)

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
    """Classify message.normalized_text into a coarse content-based message_type."""
    text = message.normalized_text or ""

    if _GREETING_PATTERN.search(text):
        return "greeting"
    if _EVENT_PATTERN.search(text):
        return "event"
    if _URGENT_PATTERN.search(text) or (
        bool(signals["direct_mention"]) and _requests_response(text)
    ):
        return "urgent"
    if _PAYMENT_PATTERN.search(text):
        return "payment"
    if _PROMOTION_PATTERN.search(text):
        return "promotion"

    if message.conversation_type == "business":
        return "business_update"
    if message.conversation_type == "personal" and int(signals["source_history_count"]) == 0:
        return "unknown"
    return "personal"


def _requests_response(text: str) -> bool:
    """Return whether a mentioned message also directly asks for a response."""
    return bool(re.search(r"\bcan you\b|\bplease\b|\bwhen you get\b", text, re.IGNORECASE))


__all__ = ["ALLOWED_MESSAGE_TYPES", "select_message_type", "validate_message_type"]
