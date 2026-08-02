"""Unit tests for router.decision.content_signals.detect_content_urgency."""

import pytest

from router.decision.content_signals import detect_content_urgency


@pytest.mark.parametrize(
    "text",
    [
        "Need to close the client note before EOD",
        "escalation starts in 20 minutes",
        "Retry count crossed the alert threshold, escalation starts asap",
        "your account will be blocked within 2 hours",
        "quick heads-up before I leave",
    ],
)
def test_detects_explicit_urgency_language(text: str):
    """Genuine deadline/escalation phrases are detected as content-urgent."""
    assert detect_content_urgency(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Reached home and had dinner. Nothing urgent, talk tomorrow.",
        "Not urgent at all, just checking in.",
        "",
        "Good morning, hope your day is peaceful.",
    ],
)
def test_does_not_flag_denied_or_absent_urgency(text: str):
    """An explicit denial of urgency, or genuinely calm text, is not urgent."""
    assert detect_content_urgency(text) is False


def test_negation_guard_does_not_suppress_a_separate_genuine_urgency_phrase():
    """A denial of urgency elsewhere in the message does not clear a real one."""
    text = "Nothing urgent about the weather, but please act immediately on the account block."

    assert detect_content_urgency(text) is True
