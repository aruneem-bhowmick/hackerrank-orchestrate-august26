"""System-level checks for the decision fusion stage.

Opened by REQ-P4-01 with a fusion-only smoke case over a small synthetic
batch; extended by REQ-P4-04 with the full Decision Record assembly once
confidence, message_type, and reason are all available.
"""

from decision_signals import make_signals, make_verdict

from router.decision.pipeline import run_action_fusion
from router.personalization.evidence import EvidenceBundle


def _bundle(message_id: str, signals: dict[str, object]) -> EvidenceBundle:
    """Build a minimal EvidenceBundle wrapping one signals mapping."""
    return EvidenceBundle(message_id, (), "no relevant historical evidence", "none", signals)


def test_action_fusion_runs_over_a_small_mixed_batch_without_error():
    """A small batch spanning clean, borderline, and blocked verdicts fuses cleanly."""
    verdicts = {
        "clean": make_verdict(message_id="clean"),
        "borderline": make_verdict(message_id="borderline", risk_type="spam", risk_confidence=0.3),
        "blocked": make_verdict(message_id="blocked", is_blocked=True, risk_type="scam", risk_confidence=0.9),
    }
    evidence = {
        "clean": _bundle("clean", make_signals(value_score_adjustment=0.2)),
        "borderline": _bundle("borderline", make_signals()),
        "blocked": _bundle("blocked", make_signals(value_score_adjustment=1.0)),
    }

    results = run_action_fusion(verdicts, evidence)

    assert set(results) == {"clean", "borderline", "blocked"}
    assert results["blocked"].action == "mute"
