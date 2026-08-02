"""Unit tests for the FusionResult/DecisionRecord contract in router.decision.trace."""

from router.decision.trace import DecisionRecord, FusionResult


def test_fusion_result_normalizes_decision_basis_to_a_tuple():
    """FusionResult accepts a list but always stores an immutable tuple."""
    result = FusionResult(
        message_id="msg_1",
        action="mute",
        value_score=0.5,
        urgency_score=0.5,
        safety_confidence=0.0,
        decision_basis=["no_signals"],
    )

    assert result.decision_basis == ("no_signals",)
    assert isinstance(result.decision_basis, tuple)


def test_decision_record_normalizes_both_tuple_fields():
    """DecisionRecord accepts lists for its two tuple fields but stores tuples."""
    record = DecisionRecord(
        message_id="msg_1",
        action="notify",
        message_type="personal",
        reason="A trusted sender sent a direct request.",
        confidence=0.8,
        evidence_message_ids=["message_0001", "message_0002"],
        safety_confidence=0.0,
        value_score=0.7,
        urgency_score=0.7,
        signal_agreement=1.0,
        decision_basis=["sender_engagement_history"],
    )

    assert record.evidence_message_ids == ("message_0001", "message_0002")
    assert isinstance(record.evidence_message_ids, tuple)
    assert record.decision_basis == ("sender_engagement_history",)
    assert isinstance(record.decision_basis, tuple)
