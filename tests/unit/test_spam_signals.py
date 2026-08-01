"""Unit tests for spam/mass-forward signal detection."""

import pytest

from fixtures.safety_spam_messages import SPAM_FIXTURES
from router.safety.signals import detect_spam_signals
from router.safety.thresholds import T_SPAM


@pytest.mark.parametrize("case", SPAM_FIXTURES, ids=lambda case: case.name)
def test_spam_fixture_cases_match_expected_signals_and_threshold(case):
    """Every fixture case's matched signal names and blocking outcome are exact."""
    matches = detect_spam_signals(
        case.message_text, case.forwarded_count, case.business, case.forward_chain_open_rate
    )
    names = frozenset(signal.name for signal in matches)
    confidence = min(1.0, sum(signal.weight for signal in matches))

    assert names == case.expected_signal_names
    assert (confidence >= T_SPAM) == case.expected_is_blocked


def test_low_forward_chain_engagement_never_fires_below_the_forward_count_threshold():
    """A low open rate alone, without a high forwarded_count, does not fire."""
    matches = detect_spam_signals(
        "Just a normal note.", forwarded_count=1, business=None, forward_chain_open_rate=0.01
    )
    names = {signal.name for signal in matches}
    assert "low_forward_chain_engagement" not in names


def test_business_none_skips_business_scoped_detectors():
    """With business=None, only text/forwarded_count detectors can fire."""
    matches = detect_spam_signals(
        "50% off everything, hurry, it may end soon.",
        forwarded_count=0,
        business=None,
        forward_chain_open_rate=None,
    )
    names = {signal.name for signal in matches}
    assert "repetitive_business_promotion" not in names
    assert "high_volume_broadcast" not in names


def test_forwarded_count_zero_does_not_count_as_high():
    """forwarded_count=0 is below the mass-forward threshold and fires nothing."""
    matches = detect_spam_signals(
        "Just checking in.", forwarded_count=0, business=None, forward_chain_open_rate=None
    )
    assert matches == []
