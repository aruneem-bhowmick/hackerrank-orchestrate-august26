"""Integration tests for evidence retrieval and loaded personalization data."""

from pathlib import Path

from router.dataset.loader import load_dataset_bundle
from router.dataset.timeline import build_user_timelines
from router.ingestion.message import NormalizedMessage
from router.personalization.pipeline import personalize_message, run_personalization


def _normalized_from_row(row: dict) -> NormalizedMessage:
    """Convert a text dataset row to the P2 contract without external media calls."""
    return NormalizedMessage(
        message_id=row["message_id"], user_id=row["user_id"], conversation_type=row["conversation_type"],
        group_id=row["group_id"], business_id=row["business_id"], sender_user_id=row["sender_user_id"],
        created_at=row["created_at"], media_type=row["media_type"], normalized_text=row["message_text"],
        media_confidence=1.0, media_failure=False, media_category=None, media_failure_reason=None,
    )


def test_pipeline_keeps_evidence_in_the_receiving_users_history() -> None:
    """REQ-P3-01: an assembled bundle cannot select ids absent from its own timeline."""
    bundle = load_dataset_bundle(Path("dataset"))
    timelines = build_user_timelines(bundle)
    row = bundle.messages.loc[bundle.messages["message_id"] == "msg_002"].iloc[0].to_dict()
    result = personalize_message(_normalized_from_row(row), bundle, timelines[row["user_id"]])
    own_ids = {item["message_id"] for item in timelines[row["user_id"]]}
    assert set(result.evidence_ids) <= own_ids


def test_batch_returns_one_bundle_per_normalized_message() -> None:
    """REQ-P3-01/05: the real loaded inputs compose into complete score-ready bundles."""
    bundle = load_dataset_bundle(Path("dataset"))
    timelines = build_user_timelines(bundle)
    rows = bundle.messages.head(4).to_dict("records")
    normalized = {row["message_id"]: _normalized_from_row(row) for row in rows}
    results = run_personalization(normalized, bundle, timelines)
    assert set(results) == set(normalized)
    assert all("value_score_adjustment" in item.personalization_signals for item in results.values())
