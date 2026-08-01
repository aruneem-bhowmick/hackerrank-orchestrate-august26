"""Unit tests for joining message history and events into per-user timelines."""

import pandas as pd
import pytest

from router.dataset.loader import DatasetBundle
from router.dataset.timeline import build_user_timelines
from router.errors import TimelineJoinError

_HISTORY_COLUMNS = (
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
)

_EVENT_COLUMNS = (
    "user_id",
    "message_id",
    "message_opened",
    "message_replied",
    "reaction_time_minutes",
    "notification_dismissed",
    "muted_after_message",
    "message_reported",
)


def _bundle(history_rows, event_rows):
    """Build a minimal DatasetBundle with only history/events populated."""
    empty = pd.DataFrame()
    return DatasetBundle(
        messages=empty,
        output_template=empty,
        sample_messages=empty,
        users=empty,
        groups=empty,
        group_members=empty,
        business_accounts=empty,
        user_business_history=empty,
        message_history=pd.DataFrame(history_rows, columns=list(_HISTORY_COLUMNS)),
        message_events=pd.DataFrame(event_rows, columns=list(_EVENT_COLUMNS)),
        images=empty,
        voice_notes=empty,
        daily_notification_summary=empty,
    )


def _history_row(message_id, user_id, created_at):
    """Build one message_history row dict with the given identity fields."""
    return dict(
        zip(
            _HISTORY_COLUMNS,
            (message_id, user_id, "personal", "", "", "", created_at, "hi", "", "", "0"),
        )
    )


def _event_row(message_id, user_id):
    """Build one message_events row dict with the given identity fields."""
    return dict(
        zip(_EVENT_COLUMNS, (user_id, message_id, "1", "0", "5", "0", "0", "0"))
    )


def test_build_user_timelines_groups_and_sorts_per_user():
    """Rows are grouped by user and sorted chronologically within each group."""
    history = [
        _history_row("m1", "u_a", "2026-01-02 10:00"),
        _history_row("m2", "u_a", "2026-01-01 10:00"),
        _history_row("m3", "u_b", "2026-01-01 10:00"),
    ]
    events = [
        _event_row("m1", "u_a"),
        _event_row("m2", "u_a"),
        _event_row("m3", "u_b"),
    ]
    timelines = build_user_timelines(_bundle(history, events))
    assert set(timelines) == {"u_a", "u_b"}
    assert [entry["message_id"] for entry in timelines["u_a"]] == ["m2", "m1"]


def test_build_user_timelines_keeps_history_without_a_matching_event():
    """A historical message with no event is kept, with event fields defaulted."""
    history = [_history_row("m1", "u_a", "2026-01-01 10:00")]
    timelines = build_user_timelines(_bundle(history, []))
    entry = timelines["u_a"][0]
    assert entry["message_id"] == "m1"
    assert entry["message_opened"] == ""
    assert entry["message_replied"] == ""


def test_build_user_timelines_raises_on_duplicate_message_id():
    """A message_id repeated in message_history raises before any join happens."""
    history = [
        _history_row("m1", "u_a", "2026-01-01 10:00"),
        _history_row("m1", "u_a", "2026-01-02 10:00"),
    ]
    events = [_event_row("m1", "u_a")]
    with pytest.raises(TimelineJoinError, match="m1"):
        build_user_timelines(_bundle(history, events))


def test_build_user_timelines_raises_on_orphaned_event():
    """An event with no matching historical message raises, naming the message_id."""
    history = [_history_row("m1", "u_a", "2026-01-01 10:00")]
    events = [_event_row("m1", "u_a"), _event_row("m_missing", "u_a")]
    with pytest.raises(TimelineJoinError, match="m_missing"):
        build_user_timelines(_bundle(history, events))


def test_build_user_timelines_raises_on_user_id_mismatch():
    """A shared message_id with disagreeing user_id across the two files raises."""
    history = [_history_row("m1", "u_a", "2026-01-01 10:00")]
    events = [_event_row("m1", "u_b")]
    with pytest.raises(TimelineJoinError, match="m1"):
        build_user_timelines(_bundle(history, events))
