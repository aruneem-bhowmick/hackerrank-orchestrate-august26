"""Batch entrypoints for decision fusion, mirroring the other phases' run_* shape."""

from collections.abc import Mapping

from router.decision.fusion import fuse_action
from router.decision.trace import FusionResult
from router.errors import DecisionFusionError
from router.personalization.evidence import EvidenceBundle
from router.safety.verdict import SafetyVerdict


def run_action_fusion(
    verdicts: Mapping[str, SafetyVerdict], evidence: Mapping[str, EvidenceBundle]
) -> dict[str, FusionResult]:
    """Fuse every message's verdict and evidence bundle into one FusionResult each.

    Raises DecisionFusionError if verdicts and evidence do not share the
    exact same message_id key set, or if the produced count does not
    match — a missing entry here would otherwise surface only as a
    mysterious gap much later, in the final output.
    """
    _validate_matching_keys(verdicts, evidence)

    results = {
        message_id: fuse_action(message_id, verdict, evidence[message_id].personalization_signals)
        for message_id, verdict in verdicts.items()
    }

    if len(results) != len(verdicts):
        raise DecisionFusionError(
            f"run_action_fusion produced {len(results)} result(s) for {len(verdicts)} verdict(s)."
        )

    return results


def _validate_matching_keys(
    verdicts: Mapping[str, SafetyVerdict], evidence: Mapping[str, EvidenceBundle]
) -> None:
    """Raise DecisionFusionError naming any message_id present on only one side."""
    verdict_ids, evidence_ids = set(verdicts), set(evidence)
    if verdict_ids != evidence_ids:
        missing_evidence = ", ".join(sorted(verdict_ids - evidence_ids))
        missing_verdicts = ", ".join(sorted(evidence_ids - verdict_ids))
        detail = "; ".join(
            part
            for part in (
                f"missing evidence for: {missing_evidence}" if missing_evidence else "",
                f"missing verdicts for: {missing_verdicts}" if missing_verdicts else "",
            )
            if part
        )
        raise DecisionFusionError(f"verdicts and evidence disagree on message_id set ({detail}).")
