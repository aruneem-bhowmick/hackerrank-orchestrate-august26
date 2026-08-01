"""Integration tests for router.decision.pipeline.run_action_fusion.

Includes the REQ-P1-04 regression pin: a blocked verdict combined with the
most favorable personalization signals possible must still yield "mute",
and this must never regress as decision fusion evolves.
"""

import pytest
from decision_signals import make_signals, make_verdict

from router.decision.pipeline import run_action_fusion
from router.errors import DecisionFusionError
from router.personalization.evidence import EvidenceBundle


def _bundle(message_id: str, signals: dict[str, object]) -> EvidenceBundle:
    """Build a minimal EvidenceBundle wrapping one signals mapping."""
    return EvidenceBundle(message_id, (), "no relevant historical evidence", "none", signals)


def test_run_action_fusion_produces_one_result_per_message():
    """Every verdict/evidence pair yields exactly one FusionResult."""
    verdicts = {
        "msg_1": make_verdict(message_id="msg_1"),
        "msg_2": make_verdict(message_id="msg_2", is_blocked=True, risk_type="scam", risk_confidence=0.8),
    }
    evidence = {
        "msg_1": _bundle("msg_1", make_signals()),
        "msg_2": _bundle("msg_2", make_signals()),
    }

    results = run_action_fusion(verdicts, evidence)

    assert set(results) == {"msg_1", "msg_2"}
    assert results["msg_2"].action == "mute"


def test_run_action_fusion_raises_on_mismatched_message_id_sets():
    """A verdict with no matching evidence bundle (or vice versa) raises loudly."""
    verdicts = {"msg_1": make_verdict(message_id="msg_1")}
    evidence = {"msg_other": _bundle("msg_other", make_signals())}

    with pytest.raises(DecisionFusionError) as excinfo:
        run_action_fusion(verdicts, evidence)

    assert "msg_1" in str(excinfo.value)
    assert "msg_other" in str(excinfo.value)


def test_safety_override_never_regresses_against_maximally_favorable_personalization():
    """REQ-P1-04 regression pin: perfect engagement history cannot rescue a blocked verdict."""
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
        evidence_strength=0.25,
        source_history_count=10,
    )
    evidence = {"msg_scam": _bundle("msg_scam", maximally_favorable_signals)}

    results = run_action_fusion({"msg_scam": verdict}, evidence)

    assert results["msg_scam"].action == "mute"
