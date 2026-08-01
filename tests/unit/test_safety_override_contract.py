"""Unit tests locking the safety-override guarantee: REQ-P1-04.

A high safety-gate confidence must not be reachable, downgradable, or
upgradable via anything that looks like a personalization signal — sender
popularity, business volume, or engagement history. These tests vary the
one axis that could plausibly leak such a signal through score_message's
existing parameters and confirm the verdict is unaffected.
"""

import pandas as pd

from router.safety.gate import score_message

_BUSINESS_ACCOUNTS_COLUMNS = [
    "business_id",
    "brand_name",
    "verified",
    "official_domain",
    "domain_used_by_sender",
    "domain_used_by_sender_age_days",
    "messages_sent_30d",
]


def test_identical_verdict_across_varying_business_popularity_field():
    """Varying a business's messages_sent_30d (a popularity proxy) never changes the verdict."""
    message = {
        "message_id": "msg_impersonator",
        "business_id": "business_impersonator",
        "message_text": "Please review your recent statement.",
        "forwarded_count": "0",
    }
    base_row = {
        "business_id": "business_impersonator",
        "brand_name": "Acme Bank",
        "verified": "0",
        "official_domain": "acmebank.com",
        "domain_used_by_sender": "acmebank-secure-alert.com",
        "domain_used_by_sender_age_days": "8",
    }
    low_volume = pd.DataFrame(
        [{**base_row, "messages_sent_30d": "5"}], columns=_BUSINESS_ACCOUNTS_COLUMNS
    )
    high_volume = pd.DataFrame(
        [{**base_row, "messages_sent_30d": "50000"}], columns=_BUSINESS_ACCOUNTS_COLUMNS
    )

    verdict_low = score_message(message, low_volume, None)
    verdict_high = score_message(message, high_volume, None)

    assert verdict_low == verdict_high
    assert verdict_low.is_blocked is True
