"""Unit tests for router.decision.reason.build_reason."""

import re

import pytest
from decision_signals import make_signals, make_verdict

from router.decision.reason import build_reason


def _is_bare_restatement(text: str, action: str) -> bool:
    """Return whether text is nothing but a templated restatement of action."""
    return bool(re.fullmatch(rf"this message was {action}d?\.?", text.strip(), re.IGNORECASE))


@pytest.mark.parametrize(
    ("action", "message_type", "verdict_kwargs", "decision_basis", "signals_overrides", "expected_fragment"),
    [
        (
            "mute",
            "scam",
            {"is_blocked": True, "risk_type": "scam", "risk_confidence": 0.9, "risk_signals": ("payment or credential request",)},
            ("safety_block:scam",),
            {},
            "scam-risk signals",
        ),
        (
            "mute",
            "forward",
            {"is_blocked": True, "risk_type": "spam", "risk_confidence": 0.6, "risk_signals": ("mass-forward chain language",)},
            ("safety_block:spam",),
            {},
            "repeated forwards",
        ),
        (
            "mute",
            "spam",
            {"is_blocked": True, "risk_type": "spam", "risk_confidence": 0.6, "risk_signals": ("repetitive promotion",)},
            ("safety_block:spam",),
            {},
            "spam signals",
        ),
        (
            "notify",
            "personal",
            {},
            ("muted_group_mention_override",),
            {},
            "directly mentioned",
        ),
        (
            "digest",
            "promotion",
            {"risk_type": "spam", "risk_confidence": 0.3, "risk_signals": ("repetitive promotion",)},
            ("borderline_safety_risk:spam",),
            {},
            "risk signals",
        ),
        (
            "mute",
            "promotion",
            {},
            ("sender_dismissal_history",),
            {},
            "ignored, dismissed, or muted",
        ),
        (
            "mute",
            "personal",
            {},
            ("group_muted_suppressed",),
            {},
            "muted by the user",
        ),
        (
            "digest",
            "personal",
            {},
            ("quiet_hours_suppressed",),
            {},
            "quiet hours",
        ),
        (
            "notify",
            "personal",
            {},
            ("sender_engagement_history",),
            {},
            "opened and replied to",
        ),
        (
            "digest",
            "promotion",
            {},
            ("evidence_corroboration",),
            {},
            "pattern of similar past messages",
        ),
        (
            "notify",
            "urgent",
            {},
            ("content_urgency_signal",),
            {},
            "deadline or urgency language",
        ),
    ],
)
def test_reason_names_the_driving_signal(
    action, message_type, verdict_kwargs, decision_basis, signals_overrides, expected_fragment
):
    """Every priority branch names its specific driving signal, not a generic restatement."""
    verdict = make_verdict(**verdict_kwargs)
    signals = make_signals(**signals_overrides)

    reason = build_reason(action, message_type, verdict, decision_basis, signals)

    assert expected_fragment.lower() in reason.lower()
    assert not _is_bare_restatement(reason, action)
    assert reason.strip() == reason
    assert reason.endswith(".")
    assert "\n" not in reason


@pytest.mark.parametrize(
    ("suppressive_component", "expected_phrase"),
    [
        ("sender_dismissal_history", "ignored, dismissed, or muted"),
        ("group_muted_suppressed", "muted by the user"),
        ("quiet_hours_suppressed", "quiet hours"),
    ],
)
def test_suppressive_component_is_not_named_when_action_is_notify(suppressive_component, expected_phrase):
    """A suppressive signal that did not win must not be reported as the cause of a notify."""
    verdict = make_verdict()

    reason = build_reason("notify", "personal", verdict, (suppressive_component, "sender_engagement_history"), make_signals())

    assert expected_phrase not in reason.lower()
    assert "opened and replied to" in reason.lower()


def test_muted_group_mention_override_is_not_named_when_action_is_mute():
    """An elevating signal that ultimately lost must not be reported as the cause of a mute."""
    verdict = make_verdict()

    reason = build_reason("mute", "personal", verdict, ("muted_group_mention_override", "sender_dismissal_history"), make_signals())

    assert "directly mentioned" not in reason.lower()
    assert "ignored, dismissed, or muted" in reason.lower()


def test_content_urgency_signal_is_not_named_when_action_is_mute():
    """Content urgency that did not prevent a mute must not be narrated as if it applied."""
    verdict = make_verdict()

    reason = build_reason("mute", "spam", verdict, ("content_urgency_signal", "sender_dismissal_history"), make_signals())

    assert "deadline or urgency language" not in reason.lower()
    assert "ignored, dismissed, or muted" in reason.lower()


def test_fallback_reason_for_unknown_message_type():
    """The no-signals fallback for an unfamiliar sender names unfamiliarity, not just the action."""
    verdict = make_verdict()

    reason = build_reason("digest", "unknown", verdict, ("no_signals",), make_signals())

    assert "unfamiliar" in reason.lower()
    assert not _is_bare_restatement(reason, "digest")


def test_fallback_reason_for_known_message_type():
    """The no-signals fallback for a categorized message still names what was not found."""
    verdict = make_verdict()

    reason = build_reason("digest", "event", verdict, ("no_signals",), make_signals())

    assert "event" in reason.lower()
    assert "urgency" in reason.lower()
    assert not _is_bare_restatement(reason, "digest")


def test_reason_length_is_reasonable():
    """Reason stays a short single sentence, matching dataset/sample_messages.csv style."""
    verdict = make_verdict(is_blocked=True, risk_type="scam", risk_confidence=0.9, risk_signals=("payment request",))

    reason = build_reason("mute", "scam", verdict, ("safety_block:scam",), make_signals())

    assert len(reason) < 200
