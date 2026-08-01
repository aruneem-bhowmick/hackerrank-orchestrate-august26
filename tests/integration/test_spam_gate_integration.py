"""Integration tests for spam detection and scam-vs-spam category selection."""

import pandas as pd

from router.safety.gate import score_message
from router.safety.thresholds import T_SPAM

_BUSINESS_ACCOUNTS_COLUMNS = [
    "business_id",
    "display_name",
    "brand_name",
    "category",
    "verified",
    "official_domain",
    "domain_used_by_sender",
    "account_age_days",
    "messages_sent_30d",
    "user_reports_30d",
    "domain_used_by_sender_age_days",
]


def _empty_business_accounts() -> pd.DataFrame:
    """An empty business_accounts frame with the real schema's columns."""
    return pd.DataFrame(columns=_BUSINESS_ACCOUNTS_COLUMNS)


def test_high_forward_count_with_low_engagement_blocks():
    """Chain language, a high forwarded_count, and a low aggregate open rate together block."""
    verdict = score_message(
        {
            "message_id": "msg_chain",
            "business_id": "",
            "message_text": "URGENT share with everyone before midnight for good luck. Do not break the chain.",
            "forwarded_count": "10",
        },
        _empty_business_accounts(),
        0.048,
    )
    assert verdict.is_blocked is True
    assert verdict.risk_type == "spam"
    assert verdict.risk_confidence >= T_SPAM


def test_high_forward_count_alone_stays_borderline():
    """The same chain message with no low-engagement corroboration stays borderline."""
    verdict = score_message(
        {
            "message_id": "msg_chain_no_rate",
            "business_id": "",
            "message_text": "URGENT share with everyone before midnight for good luck. Do not break the chain.",
            "forwarded_count": "10",
        },
        _empty_business_accounts(),
        None,
    )
    assert verdict.is_blocked is False
    assert verdict.risk_type == "spam"
    assert 0 < verdict.risk_confidence < T_SPAM


def test_blank_forwarded_count_parses_as_zero_and_does_not_raise():
    """A blank forwarded_count field (as loaded from CSV) is handled, not an error."""
    verdict = score_message(
        {
            "message_id": "msg_blank_forward",
            "business_id": "",
            "message_text": "Good morning, have a nice day.",
            "forwarded_count": "",
        },
        _empty_business_accounts(),
        None,
    )
    assert verdict.risk_type is None


def test_category_selection_picks_dominant_type():
    """When both a weak scam signal and a stronger spam signal fire, spam wins."""
    # verified="0": repetitive_business_promotion/high_volume_broadcast only
    # apply to an unverified business (a verified sender's promotional
    # volume is a personalization concern, not a safety-gate spam signal).
    business_accounts = pd.DataFrame(
        [
            {
                "business_id": "business_broadcast",
                "display_name": "Mega Mart",
                "brand_name": "Mega Mart",
                "category": "retail",
                "verified": "0",
                "official_domain": "megamart.example",
                "domain_used_by_sender": "megamart.example",
                "account_age_days": "1000",
                "messages_sent_30d": "5000",
                "user_reports_30d": "0",
                "domain_used_by_sender_age_days": "1000",
            }
        ],
        columns=_BUSINESS_ACCOUNTS_COLUMNS,
    )
    verdict = score_message(
        {
            "message_id": "msg_mixed",
            "business_id": "business_broadcast",
            # "act now" alone is a weak scam signal (urgent_deadline_pressure,
            # 0.20); the promotional phrasing plus this business's high
            # volume is a stronger spam signal (0.35 + 0.25 = 0.60).
            "message_text": "50% Off Won't Wait! Act now, this offer ends today.",
            "forwarded_count": "0",
        },
        business_accounts,
        None,
    )
    assert verdict.risk_type == "spam"
    assert "urgent deadline or account-suspension pressure language" not in verdict.risk_signals
