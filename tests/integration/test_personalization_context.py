"""Integration checks for real loaded context and override behavior."""

from pathlib import Path

from router.dataset.loader import load_dataset_bundle
from router.dataset.timeline import build_user_timelines
from router.ingestion.message import NormalizedMessage
from router.personalization.pipeline import run_personalization


def _as_text_message(row: dict) -> NormalizedMessage:
    """Represent a loaded row as a native-text normalized message for this test."""
    return NormalizedMessage(
        row["message_id"], row["user_id"], row["conversation_type"], row["group_id"],
        row["business_id"], row["sender_user_id"], row["created_at"], row["media_type"],
        row["message_text"], 1.0, False, None, None,
    )


def test_real_data_exposes_muted_group_direct_mention_overrides() -> None:
    """REQ-P3-06: loaded muted memberships and exact mentions produce a lift."""
    bundle = load_dataset_bundle(Path("dataset"))
    normalized = {row["message_id"]: _as_text_message(row) for row in bundle.messages.to_dict("records")}
    results = run_personalization(normalized, bundle, build_user_timelines(bundle))
    overrides = [item for item in results.values() if item.personalization_signals["mention_override"]]
    assert overrides
    assert all(item.personalization_signals["group_muted"] for item in overrides)
    assert all(item.personalization_signals["direct_mention"] for item in overrides)
    assert all(item.personalization_signals["urgency_score_adjustment"] > 0 for item in overrides)


def test_business_history_signals_stay_with_the_receiving_user() -> None:
    """REQ-P3-05: relationship facts are resolved with both user and business ids."""
    bundle = load_dataset_bundle(Path("dataset"))
    row = next(record for record in bundle.messages.to_dict("records") if record["business_id"])
    results = run_personalization({row["message_id"]: _as_text_message(row)}, bundle, build_user_timelines(bundle))
    signals = results[row["message_id"]].personalization_signals
    expected = bundle.user_business_history.loc[(bundle.user_business_history["user_id"] == row["user_id"]) & (bundle.user_business_history["business_id"] == row["business_id"])]
    assert signals["business_relationship"] == (expected.iloc[0]["why_user_knows_account"] if not expected.empty else None)
