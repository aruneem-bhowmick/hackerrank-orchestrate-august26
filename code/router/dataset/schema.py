"""Registry of the dataset files this system loads and the columns each must contain."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetFileSpec:
    """Describes one dataset file's name and the columns it must contain."""

    filename: str
    required_columns: tuple[str, ...]


DATASET_FILES: tuple[DatasetFileSpec, ...] = (
    DatasetFileSpec(
        "messages.csv",
        (
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
        ),
    ),
    DatasetFileSpec(
        "output.csv",
        (
            "message_id",
            "action",
            "message_type",
            "reason",
            "confidence",
            "evidence_message_ids",
        ),
    ),
    DatasetFileSpec(
        "sample_messages.csv",
        (
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
            "action",
            "message_type",
            "reason",
            "confidence",
            "evidence_message_ids",
        ),
    ),
    DatasetFileSpec(
        "users.csv",
        (
            "user_id",
            "do_not_disturb_window",
            "messages_opened_30d",
            "messages_replied_30d",
            "notifications_dismissed_30d",
            "messages_reported_30d",
        ),
    ),
    DatasetFileSpec(
        "groups.csv",
        (
            "group_id",
            "group_name",
            "group_type",
            "member_count",
            "admin_count",
            "created_at",
            "messages_30d",
        ),
    ),
    DatasetFileSpec(
        "group_members.csv",
        (
            "group_id",
            "user_id",
            "role",
            "joined_at",
            "messages_sent_30d",
            "messages_read_30d",
            "replies_sent_30d",
            "notifications_dismissed_30d",
            "group_muted_by_user",
        ),
    ),
    DatasetFileSpec(
        "business_accounts.csv",
        (
            "business_id",
            "display_name",
            "brand_name",
            "category",
            "verified",
            "official_domain",
            "domain_used_by_sender",
            "account_age_days",
            "messages_sent_30d",
            "user_reports_30d",
            "domain_used_by_sender_age_days",
        ),
    ),
    DatasetFileSpec(
        "user_business_history.csv",
        (
            "user_id",
            "business_id",
            "why_user_knows_account",
            "last_activity_at",
            "allows_promotions",
            "promotions_opted_out_at",
            "activity_count_180d",
            "messages_opened_30d",
            "messages_dismissed_30d",
            "messages_replied_30d",
            "last_reply_at",
        ),
    ),
    DatasetFileSpec(
        "message_history.csv",
        (
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
        ),
    ),
    DatasetFileSpec(
        "message_events.csv",
        (
            "user_id",
            "message_id",
            "message_opened",
            "message_replied",
            "reaction_time_minutes",
            "notification_dismissed",
            "muted_after_message",
            "message_reported",
        ),
    ),
    DatasetFileSpec("images.csv", ("image_id", "file_path")),
    DatasetFileSpec("voice_notes.csv", ("voice_note_id", "file_path")),
    DatasetFileSpec(
        "daily_notification_summary.csv",
        ("user_id", "date", "notifications_sent", "notifications_dismissed"),
    ),
)

DATASET_ALLOWLIST: frozenset[str] = frozenset(spec.filename for spec in DATASET_FILES)
