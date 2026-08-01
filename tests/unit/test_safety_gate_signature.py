"""Unit tests proving score_message's signature structurally excludes personalization."""

import inspect

import pandas as pd

from router.safety.gate import score_message

_PERSONALIZATION_PARAM_NAMES = frozenset(
    {
        "user_id",
        "users",
        "user_timeline",
        "timelines",
        "group_members",
        "groups",
        "message_history",
        "message_events",
        "user_business_history",
        "bundle",
    }
)


def test_score_message_signature_excludes_personalization_inputs():
    """score_message has no parameter through which personalization data could pass."""
    parameters = set(inspect.signature(score_message).parameters)
    assert parameters.isdisjoint(_PERSONALIZATION_PARAM_NAMES)


def test_score_message_signature_is_exactly_message_business_and_open_rate():
    """score_message's parameter list is the three documented arguments, nothing more."""
    parameters = list(inspect.signature(score_message).parameters)
    assert parameters == ["message", "business_accounts", "forward_chain_open_rate"]


def _minimal_message(**overrides) -> dict:
    message = {
        "message_id": "msg_smoke",
        "user_id": "u_001",
        "conversation_type": "personal",
        "group_id": "",
        "business_id": "",
        "sender_user_id": "u_002",
        "created_at": "2026-08-01 09:00",
        "message_text": "",
        "media_type": "",
        "media_id": "",
        "forwarded_count": "0",
    }
    message.update(overrides)
    return message


def test_score_message_smoke():
    """score_message runs on a minimal well-formed message without raising."""
    empty_business_accounts = pd.DataFrame(
        columns=[
            "business_id",
            "brand_name",
            "verified",
            "official_domain",
            "domain_used_by_sender",
            "domain_used_by_sender_age_days",
            "messages_sent_30d",
        ]
    )
    verdict = score_message(_minimal_message(), empty_business_accounts, None)
    assert verdict.message_id == "msg_smoke"
    assert verdict.is_blocked is False
    assert verdict.risk_type is None
    assert verdict.risk_confidence == 0.0
    assert verdict.risk_signals == []


def test_score_message_is_deterministic_across_repeated_calls():
    """Re-running score_message on the identical input returns an equal verdict."""
    empty_business_accounts = pd.DataFrame(
        columns=[
            "business_id",
            "brand_name",
            "verified",
            "official_domain",
            "domain_used_by_sender",
            "domain_used_by_sender_age_days",
            "messages_sent_30d",
        ]
    )
    message = _minimal_message(message_text="Reminder about tomorrow's meeting.")
    first = score_message(message, empty_business_accounts, None)
    second = score_message(message, empty_business_accounts, None)
    assert first == second
