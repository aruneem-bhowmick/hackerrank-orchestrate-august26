"""Named threshold and weight constants decision fusion scores messages against.

Pre-calibration values are documented as such; see SPEC.md ADR-004 for the
calibration pass run once every requirement in this stage is implemented.
"""

BASE_SCORE: float = 0.5
"""The neutral starting point for value_score/urgency_score before any
personalization adjustment is applied — a message with no personalization
signal at all lands exactly here, not at an arbitrary extreme."""

T_NOTIFY: float = 0.62
"""Fused priority score (0.5*value_score + 0.5*urgency_score) at/above which
action is "notify". Pre-calibration assumption; see SPEC.md ADR-004."""

T_DIGEST: float = 0.35
"""Fused priority score at/above which action is "digest" (below this,
"mute"). Pre-calibration assumption; see SPEC.md ADR-004."""

BORDERLINE_RISK_PENALTY_WEIGHT: float = 0.5
"""Multiplies a borderline verdict's risk_confidence to compute the penalty
applied to both value_score and urgency_score (REQ-P1-06: a risk signal
that does not reach the blocking threshold must still visibly lower the
score, not be silently dropped). Pre-calibration assumption; see SPEC.md
ADR-004."""

CONFIDENCE_WEIGHT_SAFETY: float = 0.5
"""Weight of safety-gate certainty in the confidence formula. Pre-calibration
assumption; see SPEC.md ADR-004."""

CONFIDENCE_WEIGHT_EVIDENCE: float = 0.2
"""Weight of normalized evidence retrieval strength in the confidence
formula. Pre-calibration assumption; see SPEC.md ADR-004."""

CONFIDENCE_WEIGHT_AGREEMENT: float = 0.3
"""Weight of safety/personalization signal agreement in the confidence
formula. Pre-calibration assumption; see SPEC.md ADR-004."""
