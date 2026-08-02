"""Unit tests for router.decision.fusion.fuse_action."""

from decision_signals import make_signals, make_verdict

from router.decision.fusion import fuse_action
from router.decision.thresholds import BASE_SCORE, T_DIGEST, T_NOTIFY


def test_blocked_scam_forces_mute_regardless_of_favorable_signals():
    """REQ-P1-04: a blocked scam verdict cannot be rescued by great engagement."""
    verdict = make_verdict(is_blocked=True, risk_type="scam", risk_confidence=0.9)
    signals = make_signals(value_score_adjustment=1.0, urgency_score_adjustment=1.0)

    result = fuse_action("msg_1", verdict, signals)

    assert result.action == "mute"
    assert result.decision_basis[0] == "safety_block:scam"


def test_blocked_spam_forces_mute_regardless_of_favorable_signals():
    """REQ-P1-04: a blocked spam verdict cannot be rescued by great engagement."""
    verdict = make_verdict(is_blocked=True, risk_type="spam", risk_confidence=0.7)
    signals = make_signals(value_score_adjustment=1.0, urgency_score_adjustment=1.0)

    result = fuse_action("msg_2", verdict, signals)

    assert result.action == "mute"
    assert result.decision_basis[0] == "safety_block:spam"


def test_borderline_risk_lowers_both_scores_and_is_named_in_basis():
    """REQ-P1-06: a non-blocking risk signal still visibly lowers the scores."""
    verdict = make_verdict(is_blocked=False, risk_type="spam", risk_confidence=0.4)
    signals = make_signals()

    result = fuse_action("msg_3", verdict, signals)

    assert result.value_score < BASE_SCORE
    assert result.urgency_score < BASE_SCORE
    assert "borderline_safety_risk:spam" in result.decision_basis


def test_clean_neutral_message_lands_exactly_on_base_score_with_no_signals_basis():
    """A clean verdict with no personalization signal is neither boosted nor penalized."""
    verdict = make_verdict()
    signals = make_signals()

    result = fuse_action("msg_4", verdict, signals)

    assert result.value_score == BASE_SCORE
    assert result.urgency_score == BASE_SCORE
    assert result.decision_basis == ("no_signals",)


def test_muted_group_with_mention_override_names_override_not_suppression():
    """REQ-P3-06: mention_override takes priority over group_muted in the basis."""
    verdict = make_verdict()
    signals = make_signals(group_muted=True, mention_override=True, urgency_score_adjustment=0.2)

    result = fuse_action("msg_5", verdict, signals)

    assert "muted_group_mention_override" in result.decision_basis
    assert "group_muted_suppressed" not in result.decision_basis


def test_muted_group_without_mention_names_suppression():
    """A muted group with no mention override is named as suppressed, not overridden."""
    verdict = make_verdict()
    signals = make_signals(group_muted=True, mention_override=False, urgency_score_adjustment=-0.4)

    result = fuse_action("msg_6", verdict, signals)

    assert "group_muted_suppressed" in result.decision_basis
    assert "muted_group_mention_override" not in result.decision_basis


def test_notify_threshold_boundary():
    """Priority exactly at T_NOTIFY yields notify; just below yields digest."""
    verdict = make_verdict()
    at_threshold = make_signals(
        value_score_adjustment=2 * (T_NOTIFY - BASE_SCORE), urgency_score_adjustment=0.0
    )
    just_below = make_signals(
        value_score_adjustment=2 * (T_NOTIFY - BASE_SCORE) - 0.02, urgency_score_adjustment=0.0
    )

    assert fuse_action("msg_7", verdict, at_threshold).action == "notify"
    assert fuse_action("msg_8", verdict, just_below).action == "digest"


def test_digest_threshold_boundary():
    """Priority exactly at T_DIGEST yields digest; just below yields mute."""
    verdict = make_verdict()
    at_threshold = make_signals(
        value_score_adjustment=2 * (T_DIGEST - BASE_SCORE), urgency_score_adjustment=0.0
    )
    just_below = make_signals(
        value_score_adjustment=2 * (T_DIGEST - BASE_SCORE) - 0.02, urgency_score_adjustment=0.0
    )

    assert fuse_action("msg_9", verdict, at_threshold).action == "digest"
    assert fuse_action("msg_10", verdict, just_below).action == "mute"


def test_fuse_action_is_deterministic():
    """Acceptance: identical inputs always yield an identical FusionResult."""
    verdict = make_verdict(is_blocked=False, risk_type="scam", risk_confidence=0.3)
    signals = make_signals(value_score_adjustment=0.2, urgency_score_adjustment=-0.1)

    first = fuse_action("msg_11", verdict, signals)
    second = fuse_action("msg_11", verdict, signals)

    assert first == second


def test_dismissal_and_engagement_and_evidence_named_in_basis():
    """Each named personalization component appears in decision_basis when active."""
    verdict = make_verdict()
    signals = make_signals(dismissal_penalty=-0.3, engagement_lift=0.1, evidence_strength=0.1)

    result = fuse_action("msg_12", verdict, signals)

    assert "sender_dismissal_history" in result.decision_basis
    assert "sender_engagement_history" in result.decision_basis
    assert "evidence_corroboration" in result.decision_basis


def test_quiet_hours_named_in_basis():
    """A quiet-hours suppression is named even without any other active signal."""
    verdict = make_verdict()
    signals = make_signals(quiet_hours=True, urgency_score_adjustment=-0.25)

    result = fuse_action("msg_13", verdict, signals)

    assert "quiet_hours_suppressed" in result.decision_basis


def test_content_urgency_boosts_urgency_score_and_is_named_in_basis():
    """A message-content urgency signal raises urgency_score above baseline."""
    verdict = make_verdict()
    signals = make_signals()

    without_urgency = fuse_action("msg_14", verdict, signals, content_urgency=False)
    with_urgency = fuse_action("msg_15", verdict, signals, content_urgency=True)

    assert with_urgency.urgency_score > without_urgency.urgency_score
    assert "content_urgency_signal" in with_urgency.decision_basis
    assert "content_urgency_signal" not in without_urgency.decision_basis


def test_content_urgency_alone_can_be_the_only_basis_component():
    """Content urgency with otherwise-neutral signals still names a real basis."""
    verdict = make_verdict()
    signals = make_signals()

    result = fuse_action("msg_16", verdict, signals, content_urgency=True)

    assert result.decision_basis == ("content_urgency_signal",)


def test_safety_override_never_regresses_against_maximally_favorable_signals():
    """REQ-P1-04 regression pin: no combination of favorable signals, including
    content urgency, can rescue a blocked verdict from "mute". Must never
    regress as decision fusion evolves."""
    verdict = make_verdict(
        message_id="msg_scam",
        is_blocked=True,
        risk_type="scam",
        risk_confidence=0.95,
        risk_signals=("payment or credential request",),
    )
    maximally_favorable_signals = make_signals(
        group_role="admin",
        value_score_adjustment=1.0,
        urgency_score_adjustment=1.0,
        open_rate=1.0,
        reply_rate=1.0,
        dismiss_rate=0.0,
        engagement_lift=0.5,
        evidence_strength=0.25,
        source_history_count=10,
    )

    result = fuse_action("msg_scam", verdict, maximally_favorable_signals, content_urgency=True)

    assert result.action == "mute"
