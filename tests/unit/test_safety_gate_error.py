"""Unit tests for run_safety_gate's cardinality guard and its error type."""

import pandas as pd
import pytest

from router.dataset.loader import DatasetBundle
from router.errors import DatasetError, SafetyGateError
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


def _bundle_with_duplicate_message_id() -> DatasetBundle:
    """A DatasetBundle whose messages frame has a duplicate message_id."""
    messages = pd.DataFrame(
        [
            ("msg_dup", "u_1", "personal", "", "", "u_2", "2026-08-01 09:00", "hi", "", "", "0"),
            ("msg_dup", "u_1", "personal", "", "", "u_2", "2026-08-01 09:05", "hi again", "", "", "0"),
        ],
        columns=_MESSAGES_COLUMNS,
    )
    empty = pd.DataFrame()
    return DatasetBundle(
        messages=messages,
        output_template=empty,
        sample_messages=empty,
        users=empty,
        groups=empty,
        group_members=empty,
        business_accounts=pd.DataFrame(columns=_BUSINESS_ACCOUNTS_COLUMNS),
        user_business_history=empty,
        message_history=pd.DataFrame(columns=["message_id", "user_id", "forwarded_count"]),
        message_events=pd.DataFrame(columns=["message_id", "user_id", "message_opened"]),
        images=empty,
        voice_notes=empty,
        daily_notification_summary=empty,
    )


def test_run_safety_gate_raises_safety_gate_error_on_duplicate_message_id():
    """A duplicate message_id raises SafetyGateError, not a bare AssertionError."""
    with pytest.raises(SafetyGateError, match="duplicate message_id"):
        run_safety_gate(_bundle_with_duplicate_message_id())


def test_safety_gate_error_is_a_dataset_error():
    """SafetyGateError is catchable alongside every other dataset-stage failure."""
    assert issubclass(SafetyGateError, DatasetError)
