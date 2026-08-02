"""Unit tests for receiver-scoped dual-signal evidence retrieval."""

from router.ingestion.message import NormalizedMessage
from router.personalization.evidence import EvidenceBundle, evidence_ids_for_output, no_evidence_bundle
from router.personalization import retrieval
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


def test_tfidf_assigns_zero_weight_to_query_only_terms() -> None:
    """REQ-P3-02: query-only terms do not enter the document-frequency corpus."""
    assert tfidf_cosine_similarity("query_only", ["known document"]) == [0.0]


def test_retrieval_fits_similarity_against_the_complete_timeline(monkeypatch) -> None:
    """REQ-P3-02: unrelated rows remain in the receiver's TF-IDF corpus."""
    captured: list[list[str]] = []

    def _scores(query: str, documents: list[str]) -> list[float]:
        """Record the fitted corpus and return one score per timeline row."""
        captured.append(documents)
        return [0.9, 0.0]

    monkeypatch.setattr(retrieval, "tfidf_cosine_similarity", _scores)
    timeline = [
        {"message_id": "history_1", "sender_user_id": "s_1", "business_id": "", "group_id": "g_1", "message_text": "matching text", "created_at": "2026-07-01"},
        {"message_id": "other_source", "sender_user_id": "s_2", "business_id": "", "group_id": "g_2", "message_text": "unrelated corpus text", "created_at": "2026-07-02"},
    ]
    result = retrieve_evidence(_message(), timeline)
    assert captured == [["matching text", "unrelated corpus text"]]
    assert result.evidence_ids == ("history_1",)


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


def test_multiple_evidence_ids_serialize_with_semicolons() -> None:
    """REQ-P3-04: output evidence follows the participant-facing delimiter contract."""
    bundle = EvidenceBundle(
        "incoming", ("history_1", "history_2"), "source_and_tfidf", "tfidf", {}
    )

    assert evidence_ids_for_output(bundle) == "history_1;history_2"


def test_no_evidence_bundle_preserves_id_and_signal_mapping() -> None:
    """REQ-P3-04: the no-match factory retains the message and score inputs."""
    signals = {"value_score_adjustment": -0.25, "urgency_score_adjustment": 0.0}
    bundle = no_evidence_bundle("incoming", signals)
    assert bundle.message_id == "incoming"
    assert bundle.evidence_ids == ()
    assert bundle.retrieval_method == "none"
    assert bundle.personalization_signals is signals
