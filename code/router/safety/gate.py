"""Scores individual messages for safety risk, independent of any receiving user."""

import pandas as pd

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
    """
    return SafetyVerdict(
        message_id=message["message_id"],
        is_blocked=False,
        risk_type=None,
        risk_confidence=0.0,
        risk_signals=[],
    )
