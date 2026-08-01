"""Unit tests for router.decision.confidence."""

from decision_signals import make_signals, make_verdict

from router.decision.confidence import compute_confidence, compute_signal_agreement
from router.decision.thresholds import (
    CONFIDENCE_WEIGHT_AGREEMENT,
    CONFIDENCE_WEIGHT_EVIDENCE,
    CONFIDENCE_WEIGHT_SAFETY,
)
from router.personalization.signals import MAX_EVIDENCE_STRENGTH


def test_clean_message_with_no_evidence_combines_safety_and_agreement_only():
    """A clean, unremarkable message gets exactly the safety+agreement weight."""
    verdict = make_verdict()
    signals = make_signals()

    confidence = compute_confidence(verdict, signals)

    assert confidence == round(CONFIDENCE_WEIGHT_SAFETY + CONFIDENCE_WEIGHT_AGREEMENT, 6)


def test_full_evidence_strength_adds_exactly_the_evidence_weight():
    """Evidence retrieval strength at its documented maximum adds its full weight."""
    verdict = make_verdict()
    zero_evidence = compute_confidence(verdict, make_signals())
    full_evidence = compute_confidence(verdict, make_signals(evidence_strength=MAX_EVIDENCE_STRENGTH))

    assert round(full_evidence - zero_evidence, 6) == round(CONFIDENCE_WEIGHT_EVIDENCE, 6)


def test_agreement_is_full_when_safety_gate_found_nothing():
    """No risk signal at all means there is nothing to disagree with."""
    verdict = make_verdict(risk_type=None)
    signals = make_signals(value_score_adjustment=1.0, urgency_score_adjustment=1.0)

    assert compute_signal_agreement(verdict, signals) == 1.0


def test_agreement_is_full_when_personalization_does_not_contradict_risk():
    """A risk signal with non-positive personalization lean is not a conflict."""
    verdict = make_verdict(risk_type="spam", risk_confidence=0.4)
    signals = make_signals(value_score_adjustment=-0.2, urgency_score_adjustment=-0.1)

    assert compute_signal_agreement(verdict, signals) == 1.0


def test_agreement_degrades_when_personalization_contradicts_risk():
    """Maximally positive personalization against a found risk signal disagrees fully."""
    verdict = make_verdict(risk_type="scam", risk_confidence=0.5, is_blocked=False)
    signals = make_signals(value_score_adjustment=1.0, urgency_score_adjustment=1.0)

    assert compute_signal_agreement(verdict, signals) == 0.0


def test_agreement_partial_lean_is_between_zero_and_one():
    """A moderate positive lean produces a proportionally reduced agreement."""
    verdict = make_verdict(risk_type="scam", risk_confidence=0.5, is_blocked=False)
    signals = make_signals(value_score_adjustment=0.4, urgency_score_adjustment=0.0)

    agreement = compute_signal_agreement(verdict, signals)

    assert 0.0 < agreement < 1.0
    assert agreement == round(1.0 - 0.2, 6)


def test_higher_blocked_risk_confidence_yields_higher_confidence():
    """A stronger combined scam signal is more certain than a barely-over-threshold one."""
    barely_blocked = make_verdict(is_blocked=True, risk_type="scam", risk_confidence=0.55)
    strongly_blocked = make_verdict(is_blocked=True, risk_type="scam", risk_confidence=0.95)
    signals = make_signals()

    assert compute_confidence(strongly_blocked, signals) > compute_confidence(barely_blocked, signals)


def test_confidence_stays_within_unit_interval_across_a_sweep():
    """Confidence never escapes [0, 1] across boundary and extreme inputs."""
    verdicts = [
        make_verdict(),
        make_verdict(risk_type="spam", risk_confidence=0.01),
        make_verdict(risk_type="spam", risk_confidence=0.549),
        make_verdict(is_blocked=True, risk_type="scam", risk_confidence=0.55),
        make_verdict(is_blocked=True, risk_type="scam", risk_confidence=1.0),
    ]
    signal_variants = [
        make_signals(),
        make_signals(value_score_adjustment=-1.0, urgency_score_adjustment=-1.0),
        make_signals(value_score_adjustment=1.0, urgency_score_adjustment=1.0, evidence_strength=MAX_EVIDENCE_STRENGTH),
    ]

    for verdict in verdicts:
        for signals in signal_variants:
            confidence = compute_confidence(verdict, signals)
            assert 0.0 <= confidence <= 1.0
