"""Scores individual messages for safety risk, independent of any receiving user.

Override contract: once run_safety_gate/score_message assigns
is_blocked=True to a message, no later phase may recompute or override
that verdict using personalization signals (sender engagement history,
group role, quiet hours, etc.). A later phase MAY use a borderline
verdict (is_blocked=False, risk_type set) as one input among several; it
may never downgrade a blocked verdict to unblocked, and it may never
upgrade risk_confidence past what this module computed using
personalization data this module never saw in the first place.
"""

import pandas as pd

from router.dataset.loader import DatasetBundle
from router.errors import SafetyGateError
from router.safety.message import SafetyMessage
from router.safety.signals import detect_scam_signals, detect_spam_signals
from router.safety.thresholds import FORWARD_CHAIN_COUNT_THRESHOLD, T_SCAM, T_SPAM
from router.safety.verdict import SafetyVerdict

_CONFIDENCE_DECIMAL_PLACES = 6


def score_message(
    message: dict,
    business_accounts: pd.DataFrame,
    forward_chain_open_rate: float | None,
) -> SafetyVerdict:
    """Score one message for safety risk, independent of any receiving user.

    message is one row of DatasetBundle.messages as a dict (e.g. from
    bundle.messages.to_dict("records")). The function first converts it to
    SafetyMessage, which copies only message_id, business_id, message_text,
    and forwarded_count; no receiver-scoped field is available to detector
    code after that boundary. business_accounts is sender-side, global
    business metadata. forward_chain_open_rate is an aggregate float (or
    None) for high-forwarded_count messages across the full user base.

    Borderline contract: whenever the winning risk category's combined
    signal weight is > 0, risk_type/risk_confidence/risk_signals are
    populated from it regardless of whether that weight reaches its
    blocking threshold. is_blocked=False with risk_type set and
    risk_confidence > 0 is a valid, expected verdict shape.
    """
    safety_message = SafetyMessage.from_record(message)
    business = _lookup_business(safety_message.business_id, business_accounts)
    verified_brand_names = _verified_brand_names(business_accounts)
    message_text = safety_message.message_text
    forwarded_count = _parse_forwarded_count(safety_message.forwarded_count)

    scam_matches = detect_scam_signals(message_text, business, verified_brand_names)
    scam_confidence = round(
        min(1.0, sum(signal.weight for signal in scam_matches)),
        _CONFIDENCE_DECIMAL_PLACES,
    )

    spam_matches = detect_spam_signals(
        message_text, forwarded_count, business, forward_chain_open_rate
    )
    spam_confidence = round(
        min(1.0, sum(signal.weight for signal in spam_matches)),
        _CONFIDENCE_DECIMAL_PLACES,
    )

    if scam_confidence <= 0.0 and spam_confidence <= 0.0:
        return SafetyVerdict(
            message_id=safety_message.message_id,
            is_blocked=False,
            risk_type=None,
            risk_confidence=0.0,
            risk_signals=[],
        )

    # A tie prefers "scam": SPEC.md §0 frames safety risk as the more
    # severe of the two categories, so a tie should not silently default
    # to the less severe label.
    if scam_confidence >= spam_confidence:
        risk_type, confidence, matches, threshold = "scam", scam_confidence, scam_matches, T_SCAM
    else:
        risk_type, confidence, matches, threshold = "spam", spam_confidence, spam_matches, T_SPAM

    return SafetyVerdict(
        message_id=safety_message.message_id,
        is_blocked=confidence >= threshold,
        risk_type=risk_type,
        risk_confidence=confidence,
        risk_signals=[signal.detail for signal in matches],
    )


def _parse_forwarded_count(raw: str) -> int:
    """Parse messages.csv's forwarded_count field, defaulting blank to 0."""
    return int(raw) if raw.strip().isdigit() else 0


def compute_forward_chain_open_rate(
    message_history: pd.DataFrame, message_events: pd.DataFrame
) -> float | None:
    """Aggregate historical open rate for high-forwarded_count messages.

    Joins message_history and message_events on message_id (inner join —
    rows without a matching event are excluded, they don't contribute a
    known open/not-open outcome), filters to forwarded_count >=
    FORWARD_CHAIN_COUNT_THRESHOLD, and returns the mean of
    message_opened == "1" among those rows. Returns None if no rows meet
    the forwarded_count filter (undefined rate, not zero). This aggregates
    across every user and sender in the historical data, not any one
    receiving user's own history, so it stays user-independent. Intended
    to be called once per run, not once per message.
    """
    merged = message_history.merge(message_events, on="message_id", how="inner")
    high_forward = merged[
        merged["forwarded_count"].apply(_parse_forwarded_count) >= FORWARD_CHAIN_COUNT_THRESHOLD
    ]
    if high_forward.empty:
        return None
    return (high_forward["message_opened"] == "1").mean()


def run_safety_gate(bundle: DatasetBundle) -> dict[str, SafetyVerdict]:
    """Score every message in bundle.messages; nothing is silently dropped.

    Computes forward_chain_open_rate once (via
    compute_forward_chain_open_rate on bundle.message_history/
    message_events), then calls score_message once per row of
    bundle.messages, returning a dict keyed by message_id. The returned
    dict has exactly one entry per row of bundle.messages — a missing
    verdict here would otherwise surface only as a mysterious gap much
    later, in P5's output. Raises SafetyGateError (a DatasetError, so
    code/main.py's existing error handling catches it) rather than
    crashing with an unhandled exception if that guarantee cannot hold.
    """
    forward_chain_open_rate = compute_forward_chain_open_rate(
        bundle.message_history, bundle.message_events
    )
    verdicts = {
        message["message_id"]: score_message(
            message, bundle.business_accounts, forward_chain_open_rate
        )
        for message in bundle.messages.to_dict("records")
    }

    if len(verdicts) != len(bundle.messages):
        raise SafetyGateError(
            f"run_safety_gate produced {len(verdicts)} verdict(s) for "
            f"{len(bundle.messages)} message(s) — bundle.messages likely "
            "has a duplicate message_id."
        )

    return verdicts


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
