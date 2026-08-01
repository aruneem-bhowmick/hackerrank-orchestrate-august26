"""Output contract for the safety gate: one verdict per message, per SPEC.md §1.3."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskSignal:
    """One named, weighted heuristic that fired while scoring a message.

    name is a short stable identifier (e.g. "payment_or_credential_request"),
    used for traceability back to the detector that produced it. weight is
    that signal's contribution toward risk_confidence, in [0, 1]. detail is
    the human-readable string surfaced in SafetyVerdict.risk_signals and,
    eventually, P5's reason field.
    """

    name: str
    weight: float
    detail: str


@dataclass(frozen=True)
class SafetyVerdict:
    """The Safety Verdict contract from SPEC.md §1.3.

    risk_type is "scam", "spam", or None. risk_confidence is a float in
    [0, 1]. risk_signals is always an immutable tuple, never None; empty
    when no signal fired. Constructors may accept a sequence for convenience,
    but it is copied to a tuple at the contract boundary. Serializers must
    convert it with list(verdict.risk_signals) when a JSON-style list is
    required. A verdict can have risk_type set and risk_confidence > 0 while
    is_blocked is False — the borderline case, still passed through with its
    risk context attached rather than cleared.
    """

    message_id: str
    is_blocked: bool
    risk_type: str | None
    risk_confidence: float
    risk_signals: tuple[str, ...]

    def __post_init__(self) -> None:
        """Copy risk signals to the tuple exposed by this immutable contract."""
        object.__setattr__(self, "risk_signals", tuple(self.risk_signals))
