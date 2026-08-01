"""Batch entrypoints for decision fusion, mirroring the other phases' run_* shape."""

from collections.abc import Mapping

from router.dataset.loader import DatasetBundle
from router.decision.confidence import compute_confidence, compute_signal_agreement
from router.decision.content_signals import detect_content_urgency
from router.decision.fusion import fuse_action
from router.decision.message_type import select_message_type
from router.decision.reason import build_reason
from router.decision.trace import DecisionRecord, FusionResult
from router.errors import DecisionFusionError
from router.ingestion.message import NormalizedMessage
from router.personalization.evidence import EvidenceBundle
from router.safety.gate import build_business_index, parse_forwarded_count
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


def run_decision_fusion(
    bundle: DatasetBundle,
    normalized: Mapping[str, NormalizedMessage],
    verdicts: Mapping[str, SafetyVerdict],
    evidence: Mapping[str, EvidenceBundle],
) -> dict[str, DecisionRecord]:
    """Produce one DecisionRecord per message_id in bundle.messages.

    Looks up each message's forwarded_count and business_accounts row from
    bundle (building the business index once per call, not per message),
    fuses the action, computes confidence, selects message_type, and
    builds reason, in that order, for every message. Raises
    DecisionFusionError if the four input mappings' key sets disagree with
    each other or with bundle.messages, or if the produced count does not
    match — the same defensive shape as
    run_safety_gate/run_personalization/run_media_ingestion.
    """
    message_ids = set(bundle.messages["message_id"])
    _validate_full_key_parity(message_ids, normalized, verdicts, evidence)

    business_index = build_business_index(bundle.business_accounts)
    forwarded_counts = {
        row["message_id"]: parse_forwarded_count(row.get("forwarded_count", ""))
        for row in bundle.messages.to_dict("records")
    }

    records = {
        message_id: _build_decision_record(
            message_id,
            normalized[message_id],
            verdicts[message_id],
            evidence[message_id],
            business_index.get(normalized[message_id].business_id),
            forwarded_counts[message_id],
        )
        for message_id in message_ids
    }

    if len(records) != len(message_ids):
        raise DecisionFusionError(
            f"run_decision_fusion produced {len(records)} record(s) for {len(message_ids)} message(s)."
        )

    return records


def _build_decision_record(
    message_id: str,
    message: NormalizedMessage,
    verdict: SafetyVerdict,
    evidence: EvidenceBundle,
    business: Mapping[str, object] | None,
    forwarded_count: int,
) -> DecisionRecord:
    """Assemble one message's full DecisionRecord from every prior stage's output."""
    signals = evidence.personalization_signals
    content_urgency = detect_content_urgency(message.normalized_text)
    fusion = fuse_action(message_id, verdict, signals, content_urgency)
    confidence = compute_confidence(verdict, signals)
    message_type = select_message_type(verdict, fusion.action, message, signals, business, forwarded_count)
    agreement = compute_signal_agreement(verdict, signals)
    reason = build_reason(fusion.action, message_type, verdict, fusion.decision_basis, signals)

    return DecisionRecord(
        message_id=message_id,
        action=fusion.action,
        message_type=message_type,
        reason=reason,
        confidence=confidence,
        evidence_message_ids=evidence.evidence_ids,
        safety_confidence=fusion.safety_confidence,
        value_score=fusion.value_score,
        urgency_score=fusion.urgency_score,
        signal_agreement=agreement,
        decision_basis=fusion.decision_basis,
    )


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


def _validate_full_key_parity(
    message_ids: set[str],
    normalized: Mapping[str, NormalizedMessage],
    verdicts: Mapping[str, SafetyVerdict],
    evidence: Mapping[str, EvidenceBundle],
) -> None:
    """Raise DecisionFusionError naming any mismatch among all four id sets."""
    sets = {
        "bundle.messages": message_ids,
        "normalized": set(normalized),
        "verdicts": set(verdicts),
        "evidence": set(evidence),
    }
    mismatched = {
        name: ids
        for name, ids in sets.items()
        if ids != message_ids
    }
    if mismatched:
        detail = "; ".join(f"{name} differs by {sorted(ids.symmetric_difference(message_ids))}" for name, ids in mismatched.items())
        raise DecisionFusionError(f"decision fusion inputs disagree on message_id set ({detail}).")
