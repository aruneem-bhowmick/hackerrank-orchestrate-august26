"""Registry of the dataset files this system loads and the columns each must contain."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetFileSpec:
    """Describes one dataset file: its name, required columns, and the
    DatasetBundle attribute it fills. attribute is None for specs built
    ad hoc (e.g. in tests exercising _load_csv directly) rather than
    registered in DATASET_FILES.
    """

    filename: str
    required_columns: tuple[str, ...]
    attribute: str | None = None


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
        attribute="messages",
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
        attribute="output_template",
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
        attribute="sample_messages",
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
        attribute="users",
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
        attribute="groups",
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
        attribute="group_members",
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
        attribute="business_accounts",
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
        attribute="user_business_history",
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
        attribute="message_history",
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
        attribute="message_events",
    ),
    DatasetFileSpec("images.csv", ("image_id", "file_path"), attribute="images"),
    DatasetFileSpec("voice_notes.csv", ("voice_note_id", "file_path"), attribute="voice_notes"),
    DatasetFileSpec(
        "daily_notification_summary.csv",
        ("user_id", "date", "notifications_sent", "notifications_dismissed"),
        attribute="daily_notification_summary",
    ),
)

DATASET_ALLOWLIST: frozenset[str] = frozenset(spec.filename for spec in DATASET_FILES)
