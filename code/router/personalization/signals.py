"""Derive receiver-specific context and score-ready adjustments."""

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, time

import pandas as pd

from router.dataset.loader import DatasetBundle
from router.ingestion.message import NormalizedMessage

_MENTION_TEMPLATE = r"(?<![a-z0-9_])@{user_id}(?![a-z0-9_])"
_MAX_ADJUSTMENT = 1.0
_MUTED_GROUP_URGENCY_PENALTY = -0.4


def build_personalization_signals(message: NormalizedMessage, bundle: DatasetBundle, timeline: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Return loaded receiver context plus neutral initial score adjustments."""
    member = _first_match(bundle.group_members, user_id=message.user_id, group_id=message.group_id)
    user = _first_match(bundle.users, user_id=message.user_id)
    relationship = _first_match(bundle.user_business_history, user_id=message.user_id, business_id=message.business_id)
    rates = engagement_rates(message, timeline)
    muted = _flag(member, "group_muted_by_user")
    quiet = is_quiet_hours(message.created_at, _text(user, "do_not_disturb_window"))
    return {
        "group_role": _text(member, "role") or None,
        "group_muted": muted,
        "quiet_hours": quiet,
        "direct_mention": has_direct_mention(message.normalized_text, message.user_id),
        "mention_override": False,
        "open_rate": rates["open_rate"],
        "reply_rate": rates["reply_rate"],
        "dismiss_rate": rates["dismiss_rate"],
        "source_history_count": rates["source_history_count"],
        "business_relationship": _text(relationship, "why_user_knows_account") or None,
        "allows_promotions": _flag(relationship, "allows_promotions"),
        "promotions_opted_out": bool(_text(relationship, "promotions_opted_out_at")),
        "business_activity_count": _number(relationship, "activity_count_180d"),
        "value_score_adjustment": 0.0,
        "urgency_score_adjustment": 0.0,
    }


def engagement_rates(message: NormalizedMessage, timeline: Sequence[Mapping[str, object]]) -> dict[str, float | int]:
    """Compute zero-safe source engagement rates from this receiver's history."""
    rows = [row for row in timeline if _same_source(message, row)]
    recent = sorted(rows, key=lambda row: str(row.get("created_at", "")), reverse=True)[:10]
    count = len(recent)
    return {
        "source_history_count": count,
        "open_rate": _rate(recent, "message_opened"),
        "reply_rate": _rate(recent, "message_replied"),
        "dismiss_rate": _rate(recent, "notification_dismissed"),
    }


def is_quiet_hours(created_at: str, window: str) -> bool:
    """Return whether a timestamp's local clock time falls in a configured window."""
    try:
        start_text, end_text = window.split("-", maxsplit=1)
        start, end = time.fromisoformat(start_text), time.fromisoformat(end_text)
        current = datetime.fromisoformat(created_at).time()
    except (TypeError, ValueError):
        return False
    return start <= current <= end if start <= end else current >= start or current <= end


def has_direct_mention(text: str, user_id: str) -> bool:
    """Return true only for an exact, case-insensitive @user_id mention token."""
    return bool(user_id and re.search(_MENTION_TEMPLATE.format(user_id=re.escape(user_id)), text or "", re.IGNORECASE))


def apply_score_adjustments(signals: dict[str, object], evidence_count: int, mean_relevance: float) -> dict[str, object]:
    """Attach bounded value and urgency adjustments with named causal components."""
    dismissal_penalty = -0.45 * float(signals["dismiss_rate"]) if evidence_count else 0.0
    engagement_lift = 0.25 * float(signals["open_rate"]) + 0.25 * float(signals["reply_rate"]) if evidence_count else 0.0
    evidence_strength = min(0.25, evidence_count * mean_relevance * 0.12)
    quiet_hours_penalty = -0.25 if signals["quiet_hours"] else 0.0
    group_muted_penalty = _MUTED_GROUP_URGENCY_PENALTY if signals["group_muted"] else 0.0
    mention_lift = 0.6 if signals["group_muted"] and signals["direct_mention"] else 0.0
    signals.update({
        "evidence_strength": round(evidence_strength, 6),
        "dismissal_penalty": round(dismissal_penalty, 6),
        "engagement_lift": round(engagement_lift, 6),
        "quiet_hours_penalty": quiet_hours_penalty,
        "group_muted_penalty": group_muted_penalty,
        "mention_override_lift": mention_lift,
        "mention_override": bool(mention_lift),
        "value_score_adjustment": round(_bound(dismissal_penalty + engagement_lift + evidence_strength), 6),
        "urgency_score_adjustment": round(
            _bound(quiet_hours_penalty + group_muted_penalty + mention_lift),
            6,
        ),
    })
    return signals


def _first_match(frame: pd.DataFrame, **conditions: str) -> Mapping[str, object] | None:
    """Return the first exact-match loaded row, or None when no relation exists."""
    selected = frame
    for column, value in conditions.items():
        if not value:
            return None
        selected = selected.loc[selected[column] == value]
    return selected.iloc[0].to_dict() if not selected.empty else None


def _same_source(message: NormalizedMessage, row: Mapping[str, object]) -> bool:
    """Match the most specific available sender, business, or group identity."""
    if message.sender_user_id:
        return message.sender_user_id == str(row.get("sender_user_id", ""))
    if message.business_id:
        return message.business_id == str(row.get("business_id", ""))
    return bool(message.group_id) and message.group_id == str(row.get("group_id", ""))


def _rate(rows: Sequence[Mapping[str, object]], field: str) -> float:
    """Return the fraction of rows whose binary event field is set to one."""
    return round(sum(str(row.get(field, "")) == "1" for row in rows) / len(rows), 6) if rows else 0.0


def _text(row: Mapping[str, object] | None, field: str) -> str:
    """Return a stripped string field from an optional row."""
    value = row.get(field, "") if row else ""
    return value.strip() if isinstance(value, str) else ""


def _flag(row: Mapping[str, object] | None, field: str) -> bool:
    """Return whether a loaded binary string field has the enabled value."""
    return _text(row, field) == "1"


def _number(row: Mapping[str, object] | None, field: str) -> int:
    """Parse a nonnegative integer field with a safe zero default."""
    value = _text(row, field)
    return int(value) if value.isdigit() else 0


def _bound(value: float) -> float:
    """Clamp a score adjustment to the documented symmetric range."""
    return max(-_MAX_ADJUSTMENT, min(_MAX_ADJUSTMENT, value))
