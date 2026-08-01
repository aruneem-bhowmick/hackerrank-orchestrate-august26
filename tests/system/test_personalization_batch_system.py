"""System-level checks for the receiver-scoped personalization batch runner."""

from router.ingestion.message import NormalizedMessage
from router.personalization.pipeline import run_personalization
from router.errors import PersonalizationError
import pytest


def _message(message_id: str, user_id: str, text: str) -> NormalizedMessage:
    """Create a minimal text message for a two-receiver isolation system test."""
    return NormalizedMessage(message_id, user_id, "group", "g", "", "sender", "2026-08-01 10:00", "", text, 1.0, False, None, None)


def test_two_receivers_cannot_share_historical_evidence(load_fixture_bundle) -> None:
    """REQ-P3-01: identical incoming content never crosses a receiver boundary."""
    bundle = load_fixture_bundle("dataset_valid")
    normalized = {"a": _message("a", "u_001", "payment report review"), "b": _message("b", "u_002", "payment report review")}
    timelines = {
        "u_001": [{"message_id": "only_u1", "sender_user_id": "sender", "business_id": "", "group_id": "g", "message_text": "payment report review", "created_at": "2026-07-01", "message_opened": "0", "message_replied": "0", "notification_dismissed": "1"}],
        "u_002": [],
    }
    result = run_personalization(normalized, bundle, timelines)
    assert result["a"].evidence_ids == ("only_u1",)
    assert result["b"].evidence_ids == ()
    assert result["b"].retrieval_method == "none"


def test_batch_rejects_duplicate_internal_message_ids() -> None:
    """REQ-P3-01: identifier parity rejects duplicated values before scoring."""
    normalized = {"first": _message("first", "u_001", "one"), "second": _message("first", "u_002", "two")}
    with pytest.raises(PersonalizationError, match="duplicate message_id"):
        run_personalization(normalized, None, {})


def test_batch_rejects_mapping_keys_that_differ_from_message_ids() -> None:
    """REQ-P3-01: identifier parity rejects a key/id mismatch before scoring."""
    with pytest.raises(PersonalizationError, match="does not match"):
        run_personalization({"wrong": _message("right", "u_001", "one")}, None, {})
