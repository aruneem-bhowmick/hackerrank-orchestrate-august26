"""Assemble receiver-scoped evidence bundles for all incoming messages."""

from collections.abc import Mapping

from router.dataset.identifiers import find_duplicates, find_mismatched_mapping_keys
from router.dataset.loader import DatasetBundle
from router.dataset.timeline import UserTimeline
from router.errors import PersonalizationError
from router.ingestion.message import NormalizedMessage
from router.personalization.evidence import EvidenceBundle, no_evidence_bundle
from router.personalization.retrieval import retrieve_evidence
from router.personalization.signals import apply_score_adjustments, build_personalization_signals


def personalize_message(message: NormalizedMessage, bundle: DatasetBundle, timeline: list[dict]) -> EvidenceBundle:
    """Produce one Evidence Bundle using only the supplied receiver timeline."""
    signals = build_personalization_signals(message, bundle, timeline)
    result = retrieve_evidence(message, timeline)
    adjusted = apply_score_adjustments(signals, len(result.evidence_ids), result.mean_relevance)
    if not result.evidence_ids:
        return no_evidence_bundle(message.message_id, adjusted)
    return EvidenceBundle(message.message_id, result.evidence_ids, result.evidence_basis, result.retrieval_method, adjusted)


def run_personalization(normalized: Mapping[str, NormalizedMessage], bundle: DatasetBundle, timelines: UserTimeline) -> dict[str, EvidenceBundle]:
    """Return exactly one receiver-scoped Evidence Bundle per normalized message."""
    _validate_identifier_parity(normalized)
    bundles = {message_id: personalize_message(message, bundle, timelines.get(message.user_id, [])) for message_id, message in normalized.items()}
    if len(bundles) != len(normalized):
        raise PersonalizationError(f"run_personalization produced {len(bundles)} bundle(s) for {len(normalized)} normalized message(s).")
    return bundles


def _validate_identifier_parity(normalized: Mapping[str, NormalizedMessage]) -> None:
    """Reject duplicate internal ids and mapping keys that do not match them."""
    message_ids = [message.message_id for message in normalized.values()]
    if find_duplicates(message_ids):
        raise PersonalizationError("normalized messages contain duplicate message_id values.")

    inconsistent = find_mismatched_mapping_keys(normalized, id_of=lambda message: message.message_id)
    if inconsistent:
        key = inconsistent[0]
        raise PersonalizationError(
            f"normalized mapping key '{key}' does not match message_id '{normalized[key].message_id}'."
        )
