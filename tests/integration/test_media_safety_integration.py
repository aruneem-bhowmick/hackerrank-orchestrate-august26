"""Integration coverage for safety scoring of normalized media content."""

import pytest

from router.ingestion.message import NormalizedMessage
from router.safety.gate import run_safety_gate


def _normalized(row: dict[str, str], text: str) -> NormalizedMessage:
    """Build the normalized contract for one loaded message using supplied text."""
    return NormalizedMessage(
        message_id=row["message_id"],
        user_id=row["user_id"],
        conversation_type=row["conversation_type"],
        group_id=row["group_id"],
        business_id=row["business_id"],
        sender_user_id=row["sender_user_id"],
        created_at=row["created_at"],
        media_type=row["media_type"],
        normalized_text=text,
        media_confidence=1.0,
        media_failure=False,
        media_category=None,
        media_failure_reason=None,
    )


@pytest.mark.parametrize("media_type", ["image", "voice"])
def test_media_derived_scam_text_reaches_the_safety_gate(
    load_fixture_bundle, media_type: str
) -> None:
    """Media-only phishing text remains blocked after normalization."""
    bundle = load_fixture_bundle("dataset_valid")
    rows = bundle.messages.to_dict("records")
    target = rows[0]
    target["message_text"] = ""
    target["media_type"] = media_type
    bundle.messages.iloc[0, bundle.messages.columns.get_loc("message_text")] = ""
    bundle.messages.iloc[0, bundle.messages.columns.get_loc("media_type")] = media_type
    normalized = {
        row["message_id"]: _normalized(
            row,
            "Confirm your password now, act now."
            if row["message_id"] == target["message_id"]
            else row["message_text"],
        )
        for row in rows
    }

    verdict = run_safety_gate(bundle, normalized)[target["message_id"]]

    assert verdict.is_blocked is True
    assert verdict.risk_type == "scam"
