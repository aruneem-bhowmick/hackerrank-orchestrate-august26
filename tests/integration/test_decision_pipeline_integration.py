"""Integration tests for router.decision.pipeline.run_decision_fusion."""

import pandas as pd
import pytest
from decision_signals import make_signals, make_verdict

from router.dataset.loader import DatasetBundle
from router.decision.message_type import ALLOWED_MESSAGE_TYPES
from router.decision.pipeline import run_decision_fusion
from router.errors import DecisionFusionError
from router.ingestion.message import NormalizedMessage
from router.personalization.evidence import EvidenceBundle

_EMPTY = pd.DataFrame()


def _bundle(messages: pd.DataFrame, business_accounts: pd.DataFrame) -> DatasetBundle:
    """Build a minimal DatasetBundle exercising only what decision fusion reads."""
    return DatasetBundle(
        messages=messages,
        output_template=_EMPTY,
        sample_messages=_EMPTY,
        users=_EMPTY,
        groups=_EMPTY,
        group_members=_EMPTY,
        business_accounts=business_accounts,
        user_business_history=_EMPTY,
        message_history=_EMPTY,
        message_events=_EMPTY,
        images=_EMPTY,
        voice_notes=_EMPTY,
        daily_notification_summary=_EMPTY,
    )


def _message(message_id: str, conversation_type: str = "personal", business_id: str = "", text: str = "hello") -> NormalizedMessage:
    """Build a minimal NormalizedMessage for a decision pipeline test row."""
    return NormalizedMessage(
        message_id=message_id,
        user_id="u_1",
        conversation_type=conversation_type,
        group_id="",
        business_id=business_id,
        sender_user_id="sender_1",
        created_at="2026-08-01 10:00",
        media_type="",
        normalized_text=text,
        media_confidence=1.0,
        media_failure=False,
        media_category=None,
        media_failure_reason=None,
    )


def _evidence(message_id: str, signals: dict[str, object]) -> EvidenceBundle:
    """Build a minimal EvidenceBundle wrapping one signals mapping."""
    return EvidenceBundle(message_id, (), "no relevant historical evidence", "none", signals)


def test_run_decision_fusion_produces_one_record_per_message():
    """A batch spanning a blocked, a business-mute, and a clean row all resolve."""
    messages = pd.DataFrame(
        [
            {"message_id": "scam_1", "forwarded_count": "0"},
            {"message_id": "biz_1", "forwarded_count": "0"},
            {"message_id": "clean_1", "forwarded_count": "0"},
        ]
    )
    business_accounts = pd.DataFrame([{"business_id": "business_1", "verified": "0", "brand_name": "Acme"}])
    bundle = _bundle(messages, business_accounts)

    normalized = {
        "scam_1": _message("scam_1", text="verify your OTP now"),
        "biz_1": _message("biz_1", conversation_type="business", business_id="business_1", text="50% off today"),
        "clean_1": _message("clean_1", text="Reached home, talk tomorrow"),
    }
    verdicts = {
        "scam_1": make_verdict(message_id="scam_1", is_blocked=True, risk_type="scam", risk_confidence=0.9, risk_signals=("payment or credential request",)),
        "biz_1": make_verdict(message_id="biz_1"),
        "clean_1": make_verdict(message_id="clean_1"),
    }
    evidence = {
        "scam_1": _evidence("scam_1", make_signals()),
        "biz_1": _evidence("biz_1", make_signals()),
        "clean_1": _evidence("clean_1", make_signals(source_history_count=3)),
    }

    records = run_decision_fusion(bundle, normalized, verdicts, evidence)

    assert set(records) == {"scam_1", "biz_1", "clean_1"}
    assert records["scam_1"].action == "mute"
    assert records["scam_1"].message_type == "scam"
    for record in records.values():
        assert record.message_type in ALLOWED_MESSAGE_TYPES
        assert record.reason
        assert 0.0 <= record.confidence <= 1.0


def test_reason_never_contradicts_a_notify_action_from_a_muted_group():
    """A muted group that content urgency and engagement overrode into notify
    must not have its reason claim the group's mute suppressed it — the
    exact boundary case (priority == T_NOTIFY) surfaced in code review."""
    messages = pd.DataFrame([{"message_id": "urgent_muted_group", "forwarded_count": "0"}])
    bundle = _bundle(messages, pd.DataFrame(columns=["business_id", "verified", "brand_name"]))

    normalized = {
        "urgent_muted_group": _message(
            "urgent_muted_group", conversation_type="group", text="Need this asap, please respond"
        )
    }
    verdicts = {"urgent_muted_group": make_verdict(message_id="urgent_muted_group")}
    signals = make_signals(
        group_muted=True,
        mention_override=False,
        engagement_lift=0.5,
        evidence_strength=0.25,
        value_score_adjustment=0.75,
        urgency_score_adjustment=-0.4,
    )
    evidence = {"urgent_muted_group": _evidence("urgent_muted_group", signals)}

    records = run_decision_fusion(bundle, normalized, verdicts, evidence)
    record = records["urgent_muted_group"]

    assert record.action == "notify"
    assert "muted" not in record.reason.lower()


def test_run_decision_fusion_raises_on_mismatched_message_id_sets():
    """A normalized/verdict/evidence set that disagrees with bundle.messages raises loudly."""
    messages = pd.DataFrame([{"message_id": "msg_1", "forwarded_count": "0"}])
    bundle = _bundle(messages, pd.DataFrame(columns=["business_id", "verified", "brand_name"]))

    normalized = {"msg_1": _message("msg_1")}
    verdicts = {"msg_1": make_verdict(message_id="msg_1")}
    evidence = {"msg_other": _evidence("msg_other", make_signals())}

    with pytest.raises(DecisionFusionError, match="message_id set"):
        run_decision_fusion(bundle, normalized, verdicts, evidence)
