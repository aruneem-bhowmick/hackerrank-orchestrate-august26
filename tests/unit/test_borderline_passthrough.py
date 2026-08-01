"""Unit tests for the borderline-risk passthrough contract.

A nonzero-but-below-threshold verdict must keep its risk_type,
risk_confidence, and risk_signals populated — never silently cleared just
because is_blocked ended up False. Re-run this suite after any change to
code/router/safety/gate.py's scoring logic.
"""

import pandas as pd

from router.safety.gate import score_message
from router.safety.thresholds import T_SCAM, T_SPAM

_BUSINESS_ACCOUNTS_COLUMNS = [
    "business_id",
    "brand_name",
    "verified",
    "official_domain",
    "domain_used_by_sender",
    "domain_used_by_sender_age_days",
    "messages_sent_30d",
]


def _empty_business_accounts() -> pd.DataFrame:
    """An empty business_accounts frame with the real schema's columns."""
    return pd.DataFrame(columns=_BUSINESS_ACCOUNTS_COLUMNS)


def test_weak_scam_signal_populates_risk_fields_without_blocking():
    """A single weak scam signal (0.20) stays unblocked but is not cleared."""
    verdict = score_message(
        {
            "message_id": "msg_weak_scam",
            "business_id": "",
            "message_text": "Your access will be suspended, act now.",
            "forwarded_count": "0",
        },
        _empty_business_accounts(),
        None,
    )
    assert verdict.is_blocked is False
    assert verdict.risk_type == "scam"
    assert verdict.risk_confidence == 0.20
    assert verdict.risk_signals == ["urgent deadline or account-suspension pressure language"]
    assert verdict.risk_confidence < T_SCAM


def test_weak_spam_signal_populates_risk_fields_without_blocking():
    """A single weak spam signal (0.15) stays unblocked but is not cleared."""
    verdict = score_message(
        {
            "message_id": "msg_weak_spam",
            "business_id": "",
            "message_text": "Just checking in on you today.",
            "forwarded_count": "8",
        },
        _empty_business_accounts(),
        None,
    )
    assert verdict.is_blocked is False
    assert verdict.risk_type == "spam"
    assert verdict.risk_confidence == 0.15
    assert verdict.risk_signals == ["forwarded_count is 8, a mass-forward level"]
    assert verdict.risk_confidence < T_SPAM


def test_true_zero_signal_case_is_distinguishable_from_borderline():
    """A wholly benign message clears to risk_type=None, not just is_blocked=False."""
    verdict = score_message(
        {
            "message_id": "msg_clean",
            "business_id": "",
            "message_text": "Dinner is ready whenever you're free.",
            "forwarded_count": "0",
        },
        _empty_business_accounts(),
        None,
    )
    assert verdict.is_blocked is False
    assert verdict.risk_type is None
    assert verdict.risk_confidence == 0.0
    assert verdict.risk_signals == []


def test_one_weight_unit_below_t_scam_stays_unblocked():
    """Combined weight strictly below T_SCAM does not block."""
    # payment_or_credential_request alone (0.35) is well under T_SCAM (0.55).
    verdict = score_message(
        {
            "message_id": "msg_below_threshold",
            "business_id": "",
            "message_text": "Please confirm your password.",
            "forwarded_count": "0",
        },
        _empty_business_accounts(),
        None,
    )
    assert verdict.risk_confidence < T_SCAM
    assert verdict.is_blocked is False
    assert verdict.risk_type == "scam"
