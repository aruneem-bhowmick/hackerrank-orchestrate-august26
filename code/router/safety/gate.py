"""Scores individual messages for safety risk, independent of any receiving user."""

import pandas as pd

from router.safety.signals import detect_scam_signals
from router.safety.thresholds import T_SCAM
from router.safety.verdict import SafetyVerdict


def score_message(
    message: dict,
    business_accounts: pd.DataFrame,
    forward_chain_open_rate: float | None,
) -> SafetyVerdict:
    """Score one message for safety risk, independent of any receiving user.

    message is one row of DatasetBundle.messages as a dict (e.g. from
    bundle.messages.to_dict("records")), keyed by the messages.csv column
    names. business_accounts is DatasetBundle.business_accounts verbatim —
    sender-side, global business metadata, not scoped to any receiving
    user. forward_chain_open_rate is a single precomputed float (or None
    if it cannot be computed) representing the aggregate historical open
    rate for high-forwarded_count messages across the entire user base.

    Deliberately excluded from the signature: user_id, UserTimeline,
    DatasetBundle.users, DatasetBundle.message_history,
    DatasetBundle.message_events, DatasetBundle.user_business_history,
    DatasetBundle.groups, DatasetBundle.group_members. Their absence is
    what makes the safety gate's user-independence structural rather than
    a convention someone could accidentally violate later.

    Borderline contract: whenever the winning risk category's combined
    signal weight is > 0, risk_type/risk_confidence/risk_signals are
    populated from it regardless of whether that weight reaches its
    blocking threshold. is_blocked=False with risk_type set and
    risk_confidence > 0 is a valid, expected verdict shape.
    """
    business = _lookup_business(message.get("business_id", ""), business_accounts)
    verified_brand_names = _verified_brand_names(business_accounts)

    scam_matches = detect_scam_signals(
        message.get("message_text", ""), business, verified_brand_names
    )
    scam_confidence = min(1.0, sum(signal.weight for signal in scam_matches))

    if scam_confidence <= 0.0:
        return SafetyVerdict(
            message_id=message["message_id"],
            is_blocked=False,
            risk_type=None,
            risk_confidence=0.0,
            risk_signals=[],
        )

    return SafetyVerdict(
        message_id=message["message_id"],
        is_blocked=scam_confidence >= T_SCAM,
        risk_type="scam",
        risk_confidence=scam_confidence,
        risk_signals=[signal.detail for signal in scam_matches],
    )


def _lookup_business(business_id: str, business_accounts: pd.DataFrame) -> dict | None:
    """Look up a business_accounts row by business_id, or None if absent/blank."""
    if not business_id:
        return None
    matches = business_accounts.loc[business_accounts["business_id"] == business_id]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()


def _verified_brand_names(business_accounts: pd.DataFrame) -> frozenset[str]:
    """The lowercased set of brand_name values across every verified business row."""
    verified = business_accounts.loc[business_accounts["verified"] == "1", "brand_name"]
    return frozenset(name.strip().lower() for name in verified)
