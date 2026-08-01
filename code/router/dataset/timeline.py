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
    _raise_on_duplicate_message_ids(bundle.message_history)

    merged = bundle.message_history.merge(
        bundle.message_events,
        on="message_id",
        how="outer",
        suffixes=("_history", "_events"),
        indicator=True,
    )

    _raise_on_orphaned_events(merged)
    _raise_on_user_id_mismatch(merged)

    merged = merged.sort_values("created_at")
    merged[list(_EVENT_FIELDS)] = merged[list(_EVENT_FIELDS)].fillna("")
    fields = list(_HISTORY_FIELDS) + list(_EVENT_FIELDS)

    return {
        user_id: group[fields].to_dict("records")
        for user_id, group in merged.groupby("user_id_history")
    }


def _raise_on_duplicate_message_ids(message_history: pd.DataFrame) -> None:
    """Raise TimelineJoinError if message_id is not unique in message_history.

    A duplicate would otherwise fan out silently: the outer join on
    message_id would attach the same message_events row to every
    duplicate, fabricating identical reaction data for distinct messages.
    """
    duplicate_ids = message_history["message_id"][message_history["message_id"].duplicated()]
    if not duplicate_ids.empty:
        ids = ", ".join(sorted(duplicate_ids.unique()))
        raise TimelineJoinError(f"message_history has duplicate message_id(s): {ids}")


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
