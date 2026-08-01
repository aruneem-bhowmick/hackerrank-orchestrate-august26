"""System test: the assembled safety gate over a batch spanning every outcome."""

import pandas as pd

from router.dataset.loader import DatasetBundle
from router.safety.gate import run_safety_gate

_MESSAGES_COLUMNS = [
    "message_id",
    "user_id",
    "conversation_type",
    "group_id",
    "business_id",
    "sender_user_id",
    "created_at",
    "message_text",
    "media_type",
    "media_id",
    "forwarded_count",
]

_BUSINESS_ACCOUNTS_COLUMNS = [
    "business_id",
    "brand_name",
    "verified",
    "official_domain",
    "domain_used_by_sender",
    "domain_used_by_sender_age_days",
    "messages_sent_30d",
]

_HISTORY_COLUMNS = ["message_id", "user_id", "forwarded_count"]
_EVENT_COLUMNS = ["message_id", "user_id", "message_opened"]


def _build_bundle() -> DatasetBundle:
    messages = pd.DataFrame(
        [
            (
                "msg_clean",
                "u_1",
                "personal",
                "",
                "",
                "u_2",
                "2026-08-01 09:00",
                "Dinner is ready whenever you're free.",
                "",
                "",
                "0",
            ),
            (
                "msg_borderline",
                "u_1",
                "personal",
                "",
                "",
                "u_2",
                "2026-08-01 09:05",
                "Your access will be suspended, act now.",
                "",
                "",
                "0",
            ),
            (
                "msg_scam_blocked",
                "u_1",
                "personal",
                "",
                "",
                "u_3",
                "2026-08-01 09:10",
                "Confirm your password now, act now.",
                "",
                "",
                "0",
            ),
            (
                "msg_spam_blocked",
                "u_1",
                "group",
                "group_1",
                "",
                "u_4",
                "2026-08-01 09:15",
                "URGENT share with everyone before midnight for good luck. Do not break the chain.",
                "",
                "",
                "10",
            ),
        ],
        columns=_MESSAGES_COLUMNS,
    )
    business_accounts = pd.DataFrame(columns=_BUSINESS_ACCOUNTS_COLUMNS)
    message_history = pd.DataFrame(
        [("hist_1", "u_9", "9"), ("hist_2", "u_9", "8")], columns=_HISTORY_COLUMNS
    )
    message_events = pd.DataFrame(
        [("hist_1", "u_9", "0"), ("hist_2", "u_9", "0")], columns=_EVENT_COLUMNS
    )
    empty = pd.DataFrame()
    return DatasetBundle(
        messages=messages,
        output_template=empty,
        sample_messages=empty,
        users=empty,
        groups=empty,
        group_members=empty,
        business_accounts=business_accounts,
        user_business_history=empty,
        message_history=message_history,
        message_events=message_events,
        images=empty,
        voice_notes=empty,
        daily_notification_summary=empty,
    )


def test_batch_covering_clean_borderline_and_both_blocked_categories():
    """A four-message batch sorts into clean, borderline, blocked-scam, blocked-spam."""
    verdicts = run_safety_gate(_build_bundle())

    assert verdicts["msg_clean"].risk_type is None
    assert verdicts["msg_clean"].is_blocked is False

    assert verdicts["msg_borderline"].risk_type == "scam"
    assert verdicts["msg_borderline"].is_blocked is False
    assert verdicts["msg_borderline"].risk_confidence > 0

    assert verdicts["msg_scam_blocked"].risk_type == "scam"
    assert verdicts["msg_scam_blocked"].is_blocked is True

    assert verdicts["msg_spam_blocked"].risk_type == "spam"
    assert verdicts["msg_spam_blocked"].is_blocked is True

    assert len(verdicts) == 4
