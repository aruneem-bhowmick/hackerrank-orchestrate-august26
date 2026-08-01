"""Unit tests proving score_message's signature structurally excludes personalization."""

import inspect
from dataclasses import fields

import pandas as pd

from router.safety.gate import _verified_brand_names, build_business_index, score_message
from router.safety.message import SafetyMessage
from router.safety.verdict import RiskSignal

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


def test_safety_message_allowlist_drops_user_scoped_fields_before_scoring():
    """The scorer's DTO cannot carry receiver identity, history, or group fields."""
    message = SafetyMessage.from_record(_minimal_message())

    assert [field.name for field in fields(SafetyMessage)] == [
        "message_id",
        "business_id",
        "message_text",
        "forwarded_count",
    ]
    assert not hasattr(message, "user_id")
    assert not hasattr(message, "group_id")
    assert not hasattr(message, "message_history")


def test_user_scoped_record_fields_cannot_change_safety_scoring():
    """Changing user-specific fields leaves the allowlisted safety input unchanged."""
    empty_business_accounts = pd.DataFrame(
        columns=["business_id", "verified", "brand_name"]
    )
    original = _minimal_message(message_text="Confirm your password now, act now.")
    altered = {
        **original,
        "user_id": "u_999",
        "group_id": "group_999",
        "message_history": "high engagement",
        "user_business_history": "trusted sender",
    }

    assert score_message(original, empty_business_accounts, None) == score_message(
        altered, empty_business_accounts, None
    )


def test_score_message_positional_signature_is_exactly_message_business_and_open_rate():
    """score_message's required, positional parameters are the three documented arguments.

    This is also the REQ-P1-04 signature-stability check: the contract
    locks the positional arguments a caller must supply, not the presence
    of optional keyword-only batch-hoisting hints (business_index,
    verified_brand_names) — those are perf-only, default to None, and
    carry no personalization data (see
    test_score_message_signature_excludes_personalization_inputs).
    """
    parameters = inspect.signature(score_message).parameters
    positional = [
        name
        for name, param in parameters.items()
        if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    assert positional == ["message", "business_accounts", "forward_chain_open_rate"]


def test_score_message_keyword_only_hints_are_optional_and_default_to_none():
    """The batch-hoisting hints are opt-in: omitting them falls back to per-call derivation."""
    parameters = inspect.signature(score_message).parameters
    for name in ("business_index", "verified_brand_names"):
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert parameters[name].default is None


def test_score_message_gives_identical_verdict_with_or_without_hoisted_hints():
    """Passing precomputed business_index/verified_brand_names doesn't change the outcome."""
    business_accounts = pd.DataFrame(
        [
            {
                "business_id": "business_1",
                "brand_name": "Acme",
                "verified": "0",
                "official_domain": "acme.com",
                "domain_used_by_sender": "acme-secure.com",
                "domain_used_by_sender_age_days": "5",
                "messages_sent_30d": "10",
            }
        ]
    )
    message = _minimal_message(business_id="business_1", message_text="Confirm your password now.")

    without_hints = score_message(message, business_accounts, None)
    with_hints = score_message(
        message,
        business_accounts,
        None,
        business_index=build_business_index(business_accounts),
        verified_brand_names=_verified_brand_names(business_accounts),
    )
    assert without_hints == with_hints


def _minimal_message(**overrides) -> dict:
    """A well-formed minimal messages.csv row, with any field overridable by name."""
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
    assert verdict.risk_signals == ()


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


def test_category_tie_uses_rounded_confidence_and_prefers_scam(monkeypatch):
    """Equivalent floating-point sums form a scam-preferred tie."""
    monkeypatch.setattr(
        "router.safety.gate.detect_scam_signals",
        lambda *_: [RiskSignal("scam", 0.30, "scam signal")],
    )
    monkeypatch.setattr(
        "router.safety.gate.detect_spam_signals",
        lambda *_: [RiskSignal("spam_a", 0.10, "spam signal A"), RiskSignal("spam_b", 0.20, "spam signal B")],
    )

    verdict = score_message(
        _minimal_message(), pd.DataFrame(columns=["business_id", "verified", "brand_name"]), None
    )

    assert verdict.risk_type == "scam"
    assert verdict.risk_confidence == 0.30
