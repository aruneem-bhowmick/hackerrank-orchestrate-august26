"""Shared synthetic SafetyVerdict/personalization_signals fixtures for Phase 4 tests."""

from router.safety.verdict import SafetyVerdict

NEUTRAL_SIGNALS: dict[str, object] = {
    "group_role": None,
    "group_muted": False,
    "quiet_hours": False,
    "direct_mention": False,
    "mention_override": False,
    "open_rate": 0.0,
    "reply_rate": 0.0,
    "dismiss_rate": 0.0,
    "source_history_count": 0,
    "business_relationship": None,
    "allows_promotions": False,
    "promotions_opted_out": False,
    "business_activity_count": 0,
    "value_score_adjustment": 0.0,
    "urgency_score_adjustment": 0.0,
    "evidence_strength": 0.0,
    "dismissal_penalty": 0.0,
    "engagement_lift": 0.0,
    "quiet_hours_penalty": 0.0,
    "group_muted_penalty": 0.0,
    "mention_override_lift": 0.0,
}


def make_signals(**overrides: object) -> dict[str, object]:
    """Return a full personalization_signals mapping, neutral except for overrides."""
    signals = dict(NEUTRAL_SIGNALS)
    signals.update(overrides)
    return signals


def make_verdict(
    message_id: str = "msg_test",
    is_blocked: bool = False,
    risk_type: str | None = None,
    risk_confidence: float = 0.0,
    risk_signals: tuple[str, ...] = (),
) -> SafetyVerdict:
    """Return a synthetic SafetyVerdict for a clean, borderline, or blocked case."""
    return SafetyVerdict(
        message_id=message_id,
        is_blocked=is_blocked,
        risk_type=risk_type,
        risk_confidence=risk_confidence,
        risk_signals=risk_signals,
    )
