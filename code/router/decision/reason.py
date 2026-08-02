"""Builds the short, human-readable reason string for a routing decision.

Per REQ-P4-04, reason names the specific signal(s) that drove the
decision — it is assembled from decision_basis's named components, never a
templated restatement of the action field.
"""

from collections.abc import Mapping, Sequence

from router.safety.verdict import SafetyVerdict


def build_reason(
    action: str,
    message_type: str,
    verdict: SafetyVerdict,
    decision_basis: Sequence[str],
    signals: Mapping[str, object],
) -> str:
    """Return one short, human-readable sentence naming the specific
    signal(s) that drove this decision.

    Selects the single highest-priority named component present in
    decision_basis and renders it through that component's phrase
    template, substituting concrete detail from verdict/signals where the
    template calls for it. Falls back to a content/action-derived generic
    sentence only when decision_basis is exactly ("no_signals",). Never
    raises for well-formed input.

    A basis component only names one contributing factor to value_score
    or urgency_score, not the winning factor — fuse_action can, e.g., mute
    a group and still land on "notify" if content urgency or engagement
    outweighs that penalty. So every "elevating" component (one that
    argues for a higher-priority action) is gated on action != "mute",
    and every "suppressive" component (one that argues for a lower-
    priority action) is gated on action != "notify" — a component whose
    own direction contradicts the actual action is never narrated as the
    cause.
    """
    basis_set = set(decision_basis)

    if "safety_block:scam" in basis_set:
        return (
            f"The message shows scam-risk signals ({verdict.risk_signals[0]}) "
            "and is muted regardless of sender history."
        )

    if "safety_block:spam" in basis_set:
        if message_type == "forward":
            return "The sender has a pattern of repeated forwards that this user usually ignores."
        return (
            f"The message shows spam signals ({verdict.risk_signals[0]}) "
            "and is muted regardless of sender history."
        )

    if "muted_group_mention_override" in basis_set and action != "mute":
        return "The group is muted, but you were directly mentioned, which raises this above the group's baseline."

    if "content_urgency_signal" in basis_set and action != "mute":
        return "The message contains explicit deadline or urgency language."

    borderline_component = next((item for item in decision_basis if item.startswith("borderline_safety_risk")), None)
    if borderline_component is not None and action != "mute":
        return (
            f"The message has some risk signals ({verdict.risk_signals[0]}) that lower its "
            "priority, though not enough to mute it outright."
        )

    if "sender_dismissal_history" in basis_set and action != "notify":
        return "Similar historical messages were ignored, dismissed, or muted by this user."

    if "group_muted_suppressed" in basis_set and action != "notify":
        return "This group is muted by the user, and there is no direct mention to override that."

    if "quiet_hours_suppressed" in basis_set and action != "notify":
        return "This arrived during the user's quiet hours, so it is held back rather than delivered now."

    if "sender_engagement_history" in basis_set and action == "notify":
        return "The sender has a strong history of being opened and replied to by this user."

    if "evidence_corroboration" in basis_set:
        return "This matches a pattern of similar past messages from this source."

    return _fallback_reason(message_type)


def _fallback_reason(message_type: str) -> str:
    """Return a still-concrete sentence for the no-signals-found case."""
    if message_type == "unknown":
        return "The sender is unfamiliar, and the message shows no urgency, payment pressure, or safety risk."
    return f"This {message_type} message shows no urgency, payment pressure, or safety risk for this user."
