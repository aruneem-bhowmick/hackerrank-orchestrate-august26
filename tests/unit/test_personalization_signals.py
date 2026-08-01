"""Unit tests for receiver-specific personalization signal derivation."""

from router.personalization.signals import apply_score_adjustments, has_direct_mention, is_quiet_hours


def test_quiet_hours_supports_overnight_windows() -> None:
    """REQ-P3-05: a window spanning midnight correctly recognizes both sides."""
    assert is_quiet_hours("2026-08-01 23:30", "22:00-07:00")
    assert is_quiet_hours("2026-08-01 06:30", "22:00-07:00")
    assert not is_quiet_hours("2026-08-01 12:00", "22:00-07:00")


def test_direct_mention_matches_only_the_exact_recipient() -> None:
    """REQ-P3-06: mention matching avoids longer identifier false positives."""
    assert has_direct_mention("@u_010 please review", "u_010")
    assert not has_direct_mention("@u_0100 please review", "u_010")


def test_repeated_dismissals_lower_the_value_adjustment() -> None:
    """REQ-P3-03: dismissed relevant history creates an observable penalty."""
    signals = {"dismiss_rate": 1.0, "open_rate": 0.0, "reply_rate": 0.0, "quiet_hours": False, "group_muted": False, "direct_mention": False}
    adjusted = apply_score_adjustments(signals, evidence_count=2, mean_relevance=0.5)
    assert adjusted["dismissal_penalty"] < 0
    assert adjusted["value_score_adjustment"] < 0


def test_muted_group_mention_adds_an_urgency_override() -> None:
    """REQ-P3-06: a direct mention offsets the muted group's baseline urgency."""
    signals = {"dismiss_rate": 0.0, "open_rate": 0.0, "reply_rate": 0.0, "quiet_hours": False, "group_muted": True, "direct_mention": True}
    adjusted = apply_score_adjustments(signals, evidence_count=0, mean_relevance=0.0)
    assert adjusted["mention_override"] is True
    assert adjusted["urgency_score_adjustment"] > 0
