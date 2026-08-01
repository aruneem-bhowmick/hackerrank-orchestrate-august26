"""Unit tests for scam/phishing signal detection."""

import pytest

from fixtures.safety_scam_messages import (
    ACME_BANK_VERIFIED_BRAND_NAMES,
    SCAM_FIXTURES,
    VERIFIED_ACME_BANK,
)
from router.safety.gate import score_message
from router.safety.signals import detect_scam_signals
from router.safety.thresholds import T_SCAM


@pytest.mark.parametrize("case", SCAM_FIXTURES, ids=lambda case: case.name)
def test_scam_fixture_cases_match_expected_signals_and_threshold(case):
    """Every fixture case's matched signal names and blocking outcome are exact."""
    matches = detect_scam_signals(case.message_text, case.business, case.verified_brand_names)
    names = frozenset(signal.name for signal in matches)
    confidence = min(1.0, sum(signal.weight for signal in matches))

    assert names == case.expected_signal_names
    assert (confidence >= T_SCAM) == case.expected_is_blocked


def test_business_none_skips_every_business_scoped_detector():
    """With business=None, only text-pattern detectors can fire."""
    matches = detect_scam_signals(
        "Please share your OTP now.", None, verified_brand_names=frozenset({"acme bank"})
    )
    names = {signal.name for signal in matches}
    assert names == {"payment_or_credential_request"}


def test_blank_business_fields_do_not_raise():
    """A business dict with blank optional fields is handled, not an error."""
    business = {
        "business_id": "business_1",
        "brand_name": "",
        "verified": "1",
        "official_domain": "",
        "domain_used_by_sender": "",
        "domain_used_by_sender_age_days": "",
        "messages_sent_30d": "",
    }
    matches = detect_scam_signals("Hello there.", business, frozenset())
    assert matches == []


def test_negation_only_suppresses_the_adjacent_credential_keyword():
    """A later OTP request still fires after an earlier no-OTP statement."""
    matches = detect_scam_signals(
        "No payment or OTP is required for this delivery. Reply with your OTP now.",
        None,
        frozenset(),
    )

    assert {signal.name for signal in matches} == {"payment_or_credential_request"}


def test_mixed_official_and_unfamiliar_domains_remain_suspicious():
    """An official-domain token cannot suppress a different link in the same message."""
    matches = detect_scam_signals(
        "View your statement at acmebank.com, then verify at acmebank-secure.xyz.",
        VERIFIED_ACME_BANK,
        ACME_BANK_VERIFIED_BRAND_NAMES,
    )

    assert "suspicious_link_or_domain" in {signal.name for signal in matches}


def test_threshold_boundary_blocks_at_exactly_t_scam():
    """A combined weight exactly equal to T_SCAM blocks (>=, not >)."""
    # payment_or_credential_request (0.35) + urgent_deadline_pressure (0.20) = 0.55 = T_SCAM.
    text = "Confirm your password now, act now."
    matches = detect_scam_signals(text, None, frozenset())
    confidence = min(1.0, sum(signal.weight for signal in matches))
    assert confidence == pytest.approx(T_SCAM)
    assert confidence >= T_SCAM


def test_below_threshold_single_weak_signal_does_not_block():
    """A single weak signal alone stays below T_SCAM."""
    verdict = score_message(
        {
            "message_id": "msg_weak",
            "business_id": "",
            "message_text": "Your access will be suspended, act now.",
            "forwarded_count": "0",
        },
        _empty_business_accounts(),
        None,
    )
    assert verdict.is_blocked is False
    assert verdict.risk_confidence < T_SCAM


def _empty_business_accounts():
    """An empty business_accounts frame with the real schema's columns."""
    import pandas as pd

    return pd.DataFrame(
        columns=[
            "business_id",
            "brand_name",
            "verified",
            "official_domain",
            "domain_used_by_sender",
            "domain_used_by_sender_age_days",
            "messages_sent_30d",
        ]
    )
