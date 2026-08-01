"""Unit tests for receiver-scoped dual-signal evidence retrieval."""

from router.ingestion.message import NormalizedMessage
from router.personalization.evidence import EvidenceBundle, evidence_ids_for_output
from router.personalization.retrieval import retrieve_evidence
from router.personalization.similarity import tfidf_cosine_similarity


def _message(**overrides: str) -> NormalizedMessage:
    """Build a compact normalized incoming message for retrieval tests."""
    values = {
        "message_id": "incoming", "user_id": "u_1", "conversation_type": "group",
        "group_id": "g_1", "business_id": "", "sender_user_id": "s_1",
        "created_at": "2026-08-01 10:00", "media_type": "",
        "normalized_text": "please review payment report today", "media_confidence": 1.0,
        "media_failure": False, "media_category": None, "media_failure_reason": None,
    }
    values.update(overrides)
    return NormalizedMessage(**values)


def test_tfidf_is_case_insensitive_and_zero_safe() -> None:
    """REQ-P3-02: lexical scores normalize case and blank input safely."""
    assert tfidf_cosine_similarity("PAYMENT report", ["payment REPORT"])[0] > 0.9
    assert tfidf_cosine_similarity("", ["payment report"]) == [0.0]


def test_retrieval_requires_both_source_and_text_relevance() -> None:
    """REQ-P3-02: a same-source but irrelevant historical row is rejected."""
    timeline = [{"message_id": "history_1", "sender_user_id": "s_1", "business_id": "", "group_id": "g_1", "message_text": "cat photos from last weekend", "created_at": "2026-07-01"}]
    result = retrieve_evidence(_message(), timeline)
    assert result.evidence_ids == ()
    assert result.mean_relevance == 0.0


def test_retrieval_returns_relevant_same_source_ids_only() -> None:
    """REQ-P3-01/02: relevant evidence comes only from the supplied timeline."""
    timeline = [
        {"message_id": "history_1", "sender_user_id": "s_1", "business_id": "", "group_id": "g_1", "message_text": "please review payment report before today", "created_at": "2026-07-01"},
        {"message_id": "other_user", "sender_user_id": "s_9", "business_id": "", "group_id": "g_9", "message_text": "please review payment report today", "created_at": "2026-07-02"},
    ]
    result = retrieve_evidence(_message(), timeline)
    assert result.evidence_ids == ("history_1",)
    assert "other_user" not in result.evidence_ids
    assert "sender+group" in result.evidence_basis


def test_empty_evidence_serializes_to_none() -> None:
    """REQ-P3-04: an empty bundle renders the required non-fabricated sentinel."""
    bundle = EvidenceBundle("incoming", (), "no relevant historical evidence", "source_and_tfidf", {})
    assert evidence_ids_for_output(bundle) == "none"
