"""Unit tests for the SafetyVerdict/RiskSignal output contract."""

import dataclasses

import pytest

from router.safety.verdict import RiskSignal, SafetyVerdict


def test_safety_verdict_field_shape():
    """SafetyVerdict exposes exactly the fields from SPEC.md §1.3."""
    verdict = SafetyVerdict(
        message_id="msg_1",
        is_blocked=True,
        risk_type="scam",
        risk_confidence=0.9,
        risk_signals=["payment or credential request"],
    )
    assert verdict.message_id == "msg_1"
    assert verdict.is_blocked is True
    assert verdict.risk_type == "scam"
    assert verdict.risk_confidence == 0.9
    assert verdict.risk_signals == ("payment or credential request",)


def test_safety_verdict_supports_null_risk_type_and_empty_signals():
    """A clean verdict has risk_type=None and risk_signals=(), never None."""
    verdict = SafetyVerdict(
        message_id="msg_2",
        is_blocked=False,
        risk_type=None,
        risk_confidence=0.0,
        risk_signals=[],
    )
    assert verdict.risk_type is None
    assert verdict.risk_signals == ()


def test_safety_verdict_is_frozen():
    """SafetyVerdict is immutable; mutating a field raises."""
    verdict = SafetyVerdict(
        message_id="msg_3",
        is_blocked=False,
        risk_type=None,
        risk_confidence=0.0,
        risk_signals=[],
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.is_blocked = True


def test_safety_verdict_copies_signals_to_an_immutable_tuple():
    """Callers cannot mutate the verdict through the list used at construction."""
    supplied_signals = ["payment or credential request"]
    verdict = SafetyVerdict("msg_4", True, "scam", 0.9, supplied_signals)
    supplied_signals.append("urgent deadline")

    assert verdict.risk_signals == ("payment or credential request",)
    with pytest.raises(AttributeError):
        verdict.risk_signals.append("another signal")


def test_risk_signal_field_shape():
    """RiskSignal carries name, weight, and a human-readable detail string."""
    signal = RiskSignal(name="payment_or_credential_request", weight=0.35, detail="asks for an OTP")
    assert signal.name == "payment_or_credential_request"
    assert signal.weight == 0.35
    assert signal.detail == "asks for an OTP"


def test_risk_signal_is_frozen():
    """RiskSignal is immutable; mutating a field raises."""
    signal = RiskSignal(name="x", weight=0.1, detail="y")
    with pytest.raises(dataclasses.FrozenInstanceError):
        signal.weight = 0.9
