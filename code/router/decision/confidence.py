"""Computes a documented, grounded confidence score for a routing decision.

Per REQ-P4-02, confidence combines three independently nameable
components: safety-gate certainty, normalized evidence retrieval strength,
and agreement between the safety gate's independent, rule-based verdict
and the personalization signals' independent, receiver-scoped assessment.
No component is a raw, ungrounded model output.
"""

from collections.abc import Mapping

from router.decision.thresholds import (
    CONFIDENCE_WEIGHT_AGREEMENT,
    CONFIDENCE_WEIGHT_EVIDENCE,
    CONFIDENCE_WEIGHT_SAFETY,
)
from router.personalization.signals import MAX_EVIDENCE_STRENGTH
from router.safety.verdict import SafetyVerdict

_ROUND_DECIMAL_PLACES = 6


def compute_signal_agreement(verdict: SafetyVerdict, signals: Mapping[str, object]) -> float:
    """Return, in [0, 1], whether the safety gate and personalization
    signals point the same direction.

    Returns 1.0 whenever verdict.risk_type is None — the safety gate found
    no risk at all, so there is nothing for personalization to agree or
    disagree with. Otherwise, degrades from 1.0 toward 0.0 as
    personalization's combined value/urgency adjustment increasingly
    favors engagement despite a found risk signal (blocked or borderline)
    — the more personalization contradicts the risk signal, the less
    certain the overall decision is.
    """
    if verdict.risk_type is None:
        return 1.0

    lean = _bound(
        (float(signals["value_score_adjustment"]) + float(signals["urgency_score_adjustment"])) / 2
    )
    if lean <= 0.0:
        return 1.0
    return round(max(0.0, 1.0 - lean), _ROUND_DECIMAL_PLACES)


def compute_confidence(verdict: SafetyVerdict, signals: Mapping[str, object]) -> float:
    """Return confidence in [0, 1] as a documented weighted sum of safety
    certainty, normalized evidence strength, and signal agreement.

    Never returns a raw, ungrounded number — every summand is
    independently nameable and testable (see _safety_certainty and
    compute_signal_agreement).
    """
    evidence_ratio = _bound(float(signals["evidence_strength"]) / MAX_EVIDENCE_STRENGTH)
    confidence = (
        CONFIDENCE_WEIGHT_SAFETY * _safety_certainty(verdict)
        + CONFIDENCE_WEIGHT_EVIDENCE * evidence_ratio
        + CONFIDENCE_WEIGHT_AGREEMENT * compute_signal_agreement(verdict, signals)
    )
    return round(_bound(confidence), _ROUND_DECIMAL_PLACES)


def _safety_certainty(verdict: SafetyVerdict) -> float:
    """Return how certain the safety gate is in its own verdict, in [0, 1].

    A clean verdict (no risk found at all) and a blocked verdict are both
    treated as certain outcomes, scaled by how far risk_confidence sits
    from the ambiguous middle; a borderline verdict is least certain the
    closer risk_confidence sits to the blocking threshold.
    """
    if verdict.risk_type is None:
        return 1.0
    if verdict.is_blocked:
        return verdict.risk_confidence
    return 1.0 - verdict.risk_confidence


def _bound(value: float) -> float:
    """Clamp a formula component to the documented [0, 1] range."""
    return max(0.0, min(1.0, value))
