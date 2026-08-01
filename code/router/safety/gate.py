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

from collections.abc import Mapping

import pandas as pd

from router.dataset.loader import DatasetBundle
from router.errors import SafetyGateError
from router.ingestion.message import NormalizedMessage
from router.safety.message import SafetyMessage
from router.safety.signals import detect_scam_signals, detect_spam_signals
from router.safety.thresholds import FORWARD_CHAIN_COUNT_THRESHOLD, T_SCAM, T_SPAM
from router.safety.verdict import SafetyVerdict

_CONFIDENCE_DECIMAL_PLACES = 6


def score_message(
    message: dict,
    business_accounts: pd.DataFrame,
    forward_chain_open_rate: float | None,
    *,
    business_index: dict[str, dict] | None = None,
    verified_brand_names: frozenset[str] | None = None,
) -> SafetyVerdict:
    """Score one message for safety risk, independent of any receiving user.

    message is one row of DatasetBundle.messages as a dict (e.g. from
    bundle.messages.to_dict("records")). The function first converts it to
    SafetyMessage, which copies only message_id, business_id, message_text,
    and forwarded_count; no receiver-scoped field is available to detector
    code after that boundary. business_accounts is sender-side, global
    business metadata. forward_chain_open_rate is an aggregate float (or
    None) for high-forwarded_count messages across the full user base.

    business_index and verified_brand_names are optional batch-hoisting
    hints: both are invariant across every message in a run, so
    run_safety_gate computes each once (via build_business_index and
    _verified_brand_names) and passes them through here instead of
    re-deriving them from business_accounts on every call. Pass neither
    (the default) to have score_message derive them itself — the right
    choice when scoring a single message in isolation, where the cost of
    one derivation is negligible.

    Borderline contract: whenever the winning risk category's combined
    signal weight is > 0, risk_type/risk_confidence/risk_signals are
    populated from it regardless of whether that weight reaches its
    blocking threshold. is_blocked=False with risk_type set and
    risk_confidence > 0 is a valid, expected verdict shape.
    """
    safety_message = SafetyMessage.from_record(message)
    if business_index is None:
        business = _lookup_business(safety_message.business_id, business_accounts)
    elif safety_message.business_id:
        business = business_index.get(safety_message.business_id)
    else:
        business = None
    if verified_brand_names is None:
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


def _raise_on_duplicate_message_id(frame: pd.DataFrame, frame_name: str) -> None:
    """Raise SafetyGateError if message_id is not unique in frame.

    A duplicate would otherwise fan out silently: an inner join on
    message_id would multiply that message's row(s) on the other side,
    over-weighting its contribution to the aggregate open-rate mean.
    """
    duplicate_ids = frame["message_id"][frame["message_id"].duplicated()]
    if not duplicate_ids.empty:
        ids = ", ".join(sorted(duplicate_ids.unique()))
        raise SafetyGateError(f"{frame_name} has duplicate message_id(s): {ids}")


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
    to be called once per run, not once per message. Raises
    SafetyGateError if either input has more than one row per message_id
    — an inner join on message_id would otherwise fan out and silently
    over-weight that message's contribution to the aggregate.
    """
    _raise_on_duplicate_message_id(message_history, "message_history")
    _raise_on_duplicate_message_id(message_events, "message_events")

    merged = message_history.merge(message_events, on="message_id", how="inner")
    high_forward = merged[
        merged["forwarded_count"].apply(_parse_forwarded_count) >= FORWARD_CHAIN_COUNT_THRESHOLD
    ]
    if high_forward.empty:
        return None
    return (high_forward["message_opened"] == "1").mean()


def run_safety_gate(
    bundle: DatasetBundle,
    normalized_messages: Mapping[str, NormalizedMessage] | None = None,
) -> dict[str, SafetyVerdict]:
    """Score every message with raw or normalized text; nothing is silently dropped.

    Computes forward_chain_open_rate, a business_id -> row index, and the
    verified-brand-name set once each (all invariant across the batch),
    then calls score_message once per row of bundle.messages, returning a
    dict keyed by message_id. The returned dict has exactly one entry per
    row of bundle.messages — a missing verdict here would otherwise
    surface only as a mysterious gap much later, in P5's output. Raises
    SafetyGateError (a DatasetError, so code/main.py's existing error
    handling catches it) rather than crashing with an unhandled exception
    if that guarantee cannot hold. When normalized_messages is supplied, its
    exact message-id set must match bundle.messages and normalized_text replaces
    raw message_text before the SafetyMessage allowlist boundary. This exposes
    OCR/ASR-derived content without allowing user, group, or historical
    engagement fields into safety scoring.
    """
    if normalized_messages is not None:
        _validate_normalized_messages(bundle, normalized_messages)
    forward_chain_open_rate = compute_forward_chain_open_rate(
        bundle.message_history, bundle.message_events
    )
    business_index = build_business_index(bundle.business_accounts)
    verified_brand_names = _verified_brand_names(bundle.business_accounts)
    verdicts = {
        message["message_id"]: score_message(
            _safety_record(message, normalized_messages),
            bundle.business_accounts,
            forward_chain_open_rate,
            business_index=business_index,
            verified_brand_names=verified_brand_names,
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


def _validate_normalized_messages(
    bundle: DatasetBundle, normalized_messages: Mapping[str, NormalizedMessage]
) -> None:
    """Ensure normalized content has one correctly keyed entry per loaded message."""
    message_ids = set(bundle.messages["message_id"])
    if set(normalized_messages) != message_ids:
        raise SafetyGateError("normalized messages do not match the loaded message_id set.")
    mismatched = [
        key for key, message in normalized_messages.items() if key != message.message_id
    ]
    if mismatched:
        raise SafetyGateError(
            "normalized message mapping key(s) do not match their message_id: "
            f"{', '.join(sorted(mismatched))}."
        )


def _safety_record(
    message: Mapping[str, object],
    normalized_messages: Mapping[str, NormalizedMessage] | None,
) -> dict[str, object]:
    """Return the four safety inputs, substituting normalized text when available."""
    message_id = str(message.get("message_id", ""))
    normalized_text = (
        normalized_messages[message_id].normalized_text
        if normalized_messages is not None
        else message.get("message_text", "")
    )
    return {
        "message_id": message_id,
        "business_id": message.get("business_id", ""),
        "message_text": normalized_text,
        "forwarded_count": message.get("forwarded_count", ""),
    }


def _lookup_business(business_id: str, business_accounts: pd.DataFrame) -> dict | None:
    """Look up a business_accounts row by business_id, or None if absent/blank."""
    if not business_id:
        return None
    matches = business_accounts.loc[business_accounts["business_id"] == business_id]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()


def build_business_index(business_accounts: pd.DataFrame) -> dict[str, dict]:
    """A business_id -> row-dict index, built once and reused across a batch.

    On a duplicate business_id, keeps the first occurrence — matching
    _lookup_business's own "first match" behavior, so scoring the same
    message with or without a precomputed index gives an identical
    result.
    """
    deduplicated = business_accounts.drop_duplicates(subset="business_id", keep="first")
    return {row["business_id"]: row for row in deduplicated.to_dict("records")}


def _verified_brand_names(business_accounts: pd.DataFrame) -> frozenset[str]:
    """The lowercased set of non-blank brand_name values across every verified business row.

    Blank names are excluded: two businesses that both happen to have an
    empty brand_name are not "the same brand," and including "" in this
    set would make any unverified business with a blank brand_name look
    like it's impersonating a verified one.
    """
    verified = business_accounts.loc[business_accounts["verified"] == "1", "brand_name"]
    return frozenset(name.strip().lower() for name in verified if name.strip())
