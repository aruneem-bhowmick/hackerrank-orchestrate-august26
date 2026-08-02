"""Output contracts for decision fusion: intermediate and final, per SPEC.md §1.5."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FusionResult:
    """The loggable intermediate state behind one message's `action`.

    message_id matches the source message. action is "notify", "digest",
    or "mute". value_score/urgency_score are the fused [0, 1] scores after
    applying personalization adjustments and any borderline-risk penalty.
    safety_confidence is SafetyVerdict.risk_confidence carried through
    (0.0 when risk_type is None). decision_basis is an immutable tuple of
    short, named component identifiers this action was built from — never
    empty; at minimum contains a "no_signals" marker when nothing else
    fired.
    """

    message_id: str
    action: str
    value_score: float
    urgency_score: float
    safety_confidence: float
    decision_basis: tuple[str, ...]

    def __post_init__(self) -> None:
        """Normalize decision_basis to the immutable contract representation."""
        object.__setattr__(self, "decision_basis", tuple(self.decision_basis))


@dataclass(frozen=True)
class DecisionRecord:
    """The Decision Record contract from SPEC.md §1.5 (P4's full output).

    action/message_type/reason/confidence/evidence_message_ids are exactly
    what P5 serializes into output.csv for this message_id. The remaining
    fields are loggable intermediate state, never written to output.csv.
    evidence_message_ids is empty when there is no evidence — serializing
    that to the "none" sentinel is P5's job, not this dataclass's.
    """

    message_id: str
    action: str
    message_type: str
    reason: str
    confidence: float
    evidence_message_ids: tuple[str, ...]
    safety_confidence: float
    value_score: float
    urgency_score: float
    signal_agreement: float
    decision_basis: tuple[str, ...]

    def __post_init__(self) -> None:
        """Normalize both tuple fields to this immutable contract's representation."""
        object.__setattr__(self, "evidence_message_ids", tuple(self.evidence_message_ids))
        object.__setattr__(self, "decision_basis", tuple(self.decision_basis))
