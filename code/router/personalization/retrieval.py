"""Dual-signal retrieval over one receiver's historical timeline."""

from collections.abc import Mapping, Sequence

from router.ingestion.message import NormalizedMessage
from router.personalization.evidence import RetrievalResult, no_evidence_result
from router.personalization.similarity import tfidf_cosine_similarity

MIN_TEXT_SIMILARITY = 0.08
MAX_EVIDENCE_IDS = 3


def retrieve_evidence(message: NormalizedMessage, timeline: Sequence[Mapping[str, object]]) -> RetrievalResult:
    """Return same-source and text-relevant evidence from one supplied timeline.

    Callers choose the receiver's timeline before invoking this function; the
    function deliberately accepts no all-user index, which makes accidental
    cross-user retrieval structurally difficult.
    """
    candidates = [(row, _source_basis(message, row)) for row in timeline]
    candidates = [(row, basis) for row, basis in candidates if basis]
    if not candidates:
        return no_evidence_result()
    scores = tfidf_cosine_similarity(message.normalized_text, [str(row.get("message_text", "")) for row, _ in candidates])
    matches = [(row, basis, score) for (row, basis), score in zip(candidates, scores, strict=True) if score >= MIN_TEXT_SIMILARITY]
    if not matches:
        return no_evidence_result()
    matches.sort(key=lambda item: (-item[2], str(item[0].get("created_at", "")), str(item[0].get("message_id", ""))))
    selected = matches[:MAX_EVIDENCE_IDS]
    ids = tuple(str(row["message_id"]) for row, _, _ in selected)
    bases = ", ".join(sorted({basis for _, basis, _ in selected}))
    mean = round(sum(score for _, _, score in selected) / len(selected), 6)
    return RetrievalResult(ids, f"{bases} with TF-IDF text relevance", mean)


def _source_basis(message: NormalizedMessage, history: Mapping[str, object]) -> str | None:
    """Return named matching identities, or None when sources are unrelated."""
    pairs = (("sender", message.sender_user_id, "sender_user_id"), ("business", message.business_id, "business_id"), ("group", message.group_id, "group_id"))
    matched = [name for name, value, field in pairs if value and value == str(history.get(field, ""))]
    return "+".join(matched) if matched else None
