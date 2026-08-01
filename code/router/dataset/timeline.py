"""Joins historical messages with their reaction events into per-user timelines."""

import pandas as pd

from router.dataset.loader import DatasetBundle
from router.errors import TimelineJoinError

UserTimeline = dict[str, list[dict]]

_HISTORY_FIELDS = (
    "message_id",
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

_EVENT_FIELDS = (
    "message_opened",
    "message_replied",
    "reaction_time_minutes",
    "notification_dismissed",
    "muted_after_message",
    "message_reported",
)


def build_user_timelines(bundle: DatasetBundle) -> UserTimeline:
    """Join message_history and message_events into a per-user timeline.

    Rows are sorted by created_at ascending within each user. Raises
    TimelineJoinError if a message_events row has no matching
    message_history row, or if user_id disagrees between the two files
    for the same message_id. A message_history row with no matching event
    is kept, with event fields defaulted to empty strings.
    """
    merged = bundle.message_history.merge(
        bundle.message_events,
        on="message_id",
        how="outer",
        suffixes=("_history", "_events"),
        indicator=True,
    )

    _raise_on_orphaned_events(merged)
    _raise_on_user_id_mismatch(merged)

    timelines: UserTimeline = {}
    for _, row in merged.iterrows():
        entry = {field: row[field] for field in _HISTORY_FIELDS}
        for field in _EVENT_FIELDS:
            value = row[field]
            entry[field] = "" if pd.isna(value) else value
        timelines.setdefault(row["user_id_history"], []).append(entry)

    for entries in timelines.values():
        entries.sort(key=lambda entry: entry["created_at"])

    return timelines


def _raise_on_orphaned_events(merged: pd.DataFrame) -> None:
    """Raise TimelineJoinError if any message_events row has no history match."""
    orphaned = merged.loc[merged["_merge"] == "right_only", "message_id"]
    if not orphaned.empty:
        ids = ", ".join(sorted(orphaned.unique()))
        raise TimelineJoinError(
            f"message_events references message_id(s) absent from message_history: {ids}"
        )


def _raise_on_user_id_mismatch(merged: pd.DataFrame) -> None:
    """Raise TimelineJoinError if user_id disagrees between the two files for a shared row."""
    both = merged[merged["_merge"] == "both"]
    mismatched = both[both["user_id_history"] != both["user_id_events"]]
    if not mismatched.empty:
        row = mismatched.iloc[0]
        raise TimelineJoinError(
            "message_history and message_events disagree on user_id for message_id "
            f"'{row['message_id']}': '{row['user_id_history']}' vs '{row['user_id_events']}'"
        )
