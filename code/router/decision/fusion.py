"""Fuses a safety verdict and personalization signals into a deterministic action.

Override contract: once router.safety.gate assigns is_blocked=True to a
message, fuse_action always returns action="mute" for it — no
personalization signal computed here can change that (REQ-P1-04). A
borderline verdict (risk_type set, is_blocked=False) is not an override; it
visibly lowers value_score/urgency_score instead of being dropped
(REQ-P1-06).
"""

from collections.abc import Mapping

from router.decision.thresholds import (
    BASE_SCORE,
    BORDERLINE_RISK_PENALTY_WEIGHT,
    T_DIGEST,
    T_NOTIFY,
)
from router.decision.trace import FusionResult
from router.safety.verdict import SafetyVerdict


def fuse_action(
    message_id: str, verdict: SafetyVerdict, signals: Mapping[str, object]
) -> FusionResult:
    """Deterministically fuse a safety verdict and personalization signals
    into one FusionResult.

    signals is one EvidenceBundle's personalization_signals mapping (see
    router.personalization.signals.apply_score_adjustments). Raises
    nothing for well-formed input; a missing key in signals is a
    programming error in the caller, not a data condition this function
    should mask.
    """
    value_score = _bound01(BASE_SCORE + float(signals["value_score_adjustment"]))
    urgency_score = _bound01(BASE_SCORE + float(signals["urgency_score_adjustment"]))

    borderline = verdict.risk_type is not None and not verdict.is_blocked
    if borderline:
        penalty = BORDERLINE_RISK_PENALTY_WEIGHT * verdict.risk_confidence
        value_score = _bound01(value_score - penalty)
        urgency_score = _bound01(urgency_score - penalty)

    decision_basis = _build_decision_basis(verdict, signals, borderline)

    if verdict.is_blocked:
        action = "mute"
    else:
        priority = 0.5 * value_score + 0.5 * urgency_score
        if priority >= T_NOTIFY:
            action = "notify"
        elif priority >= T_DIGEST:
            action = "digest"
        else:
            action = "mute"

    return FusionResult(
        message_id=message_id,
        action=action,
        value_score=value_score,
        urgency_score=urgency_score,
        safety_confidence=verdict.risk_confidence,
        decision_basis=decision_basis,
    )


def _build_decision_basis(
    verdict: SafetyVerdict, signals: Mapping[str, object], borderline: bool
) -> tuple[str, ...]:
    """Name every component that actually contributed to this decision.

    Reads already-computed, already-named fields rather than re-deriving
    new heuristics, so this stays a transparent index into signals that
    were already causally applied, not a decorative restatement of them.
    """
    basis: list[str] = []
    if verdict.is_blocked:
        basis.append(f"safety_block:{verdict.risk_type}")
    elif borderline:
        basis.append(f"borderline_safety_risk:{verdict.risk_type}")

    mention_override = bool(signals["mention_override"])
    group_muted = bool(signals["group_muted"])
    if mention_override:
        basis.append("muted_group_mention_override")
    elif group_muted:
        basis.append("group_muted_suppressed")

    if signals["quiet_hours"]:
        basis.append("quiet_hours_suppressed")
    if float(signals["dismissal_penalty"]) < 0:
        basis.append("sender_dismissal_history")
    if float(signals["engagement_lift"]) > 0:
        basis.append("sender_engagement_history")
    if float(signals["evidence_strength"]) > 0:
        basis.append("evidence_corroboration")

    return tuple(basis) if basis else ("no_signals",)


def _bound01(value: float) -> float:
    """Clamp a fused score to the documented [0, 1] range."""
    return max(0.0, min(1.0, value))
