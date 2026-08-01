"""Regression suite: the four real scam-typed sample rows stay blocked, permanently.

SPEC.md §4 pins this directly: "High-risk message + high-engagement sender
history → still muted." A future change to code/router/safety/ that breaks
any of these four rows' is_blocked=True outcome is a REQ-P1-04 violation by
definition — this is the permanent lock for that guarantee.
"""

import pandas as pd
import pytest

from fixtures.safety_scam_messages import SCAM_FIXTURES
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

_REAL_SCAM_ROW_NAMES = (
    "sample_msg_019_otp_leak",
    "sample_msg_020_fake_support",
    "sample_msg_052_first_message_credential_request",
    "sample_msg_053_router_injection",
)

_REAL_SCAM_ROWS = [case for case in SCAM_FIXTURES if case.name in _REAL_SCAM_ROW_NAMES]

# "Rich engagement history" and "brand-new sender" shapes for the one axis
# that could plausibly leak a popularity/trust signal through
# score_message's business_accounts parameter. All four real rows have a
# blank business_id (personal/group senders), so business_accounts content
# has zero effect either way — that is the guarantee being proven, not an
# assumption baked into the test.
_ESTABLISHED_SENDER_SHAPE = pd.DataFrame(
    [
        {
            "business_id": "business_unrelated",
            "brand_name": "Unrelated Verified Co",
            "verified": "1",
            "official_domain": "unrelated.example",
            "domain_used_by_sender": "unrelated.example",
            "domain_used_by_sender_age_days": "3000",
            "messages_sent_30d": "10000",
        }
    ],
    columns=_BUSINESS_ACCOUNTS_COLUMNS,
)
_BRAND_NEW_SENDER_SHAPE = pd.DataFrame(columns=_BUSINESS_ACCOUNTS_COLUMNS)


def test_four_real_scam_rows_are_present_for_the_regression_check():
    """Guard against the fixture module silently losing one of the four rows."""
    assert len(_REAL_SCAM_ROWS) == 4


@pytest.mark.parametrize("case", _REAL_SCAM_ROWS, ids=lambda case: case.name)
@pytest.mark.parametrize(
    ("business_accounts", "forward_chain_open_rate"),
    [
        (_ESTABLISHED_SENDER_SHAPE, 0.95),
        (_BRAND_NEW_SENDER_SHAPE, None),
    ],
    ids=["established_sender_shape", "brand_new_sender_shape"],
)
def test_high_risk_sample_rows_stay_blocked_regardless_of_engagement_shape(
    case, business_accounts, forward_chain_open_rate
):
    """Each real scam row stays is_blocked=True no matter the engagement-shaped context."""
    verdict = score_message(
        {
            "message_id": case.name,
            "business_id": "",
            "message_text": case.message_text,
            "forwarded_count": "0",
        },
        business_accounts,
        forward_chain_open_rate,
    )
    assert verdict.is_blocked is True
    assert verdict.risk_type == "scam"


def test_verdict_is_identical_across_both_engagement_shapes_per_row():
    """Beyond both staying blocked, the two shapes produce byte-identical verdicts."""
    for case in _REAL_SCAM_ROWS:
        message = {
            "message_id": case.name,
            "business_id": "",
            "message_text": case.message_text,
            "forwarded_count": "0",
        }
        established = score_message(message, _ESTABLISHED_SENDER_SHAPE, 0.95)
        brand_new = score_message(message, _BRAND_NEW_SENDER_SHAPE, None)
        assert established == brand_new
