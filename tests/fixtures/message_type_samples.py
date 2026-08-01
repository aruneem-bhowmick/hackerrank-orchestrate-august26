"""Synthetic NormalizedMessage/business fixtures for message_type selection tests."""

from router.ingestion.message import NormalizedMessage


def make_normalized_message(
    message_id: str = "msg_test",
    conversation_type: str = "personal",
    normalized_text: str = "",
    business_id: str = "",
    group_id: str = "",
    sender_user_id: str = "sender_1",
) -> NormalizedMessage:
    """Build a NormalizedMessage with the fields message_type selection reads."""
    return NormalizedMessage(
        message_id=message_id,
        user_id="u_1",
        conversation_type=conversation_type,
        group_id=group_id,
        business_id=business_id,
        sender_user_id=sender_user_id,
        created_at="2026-08-01 10:00",
        media_type="",
        normalized_text=normalized_text,
        media_confidence=1.0,
        media_failure=False,
        media_category=None,
        media_failure_reason=None,
    )


def make_business(verified: str = "1", brand_name: str = "Acme") -> dict[str, object]:
    """Build a minimal business_accounts-shaped row dict."""
    return {"business_id": "business_1", "verified": verified, "brand_name": brand_name}
