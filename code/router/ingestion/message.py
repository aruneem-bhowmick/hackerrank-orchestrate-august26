"""Output contract for media ingestion: one normalized message per input row, per SPEC.md §1.2."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedMessage:
    """The Normalized Message contract from SPEC.md §1.2, as amended by ADR-007.

    Produced for every row of DatasetBundle.messages, not just media rows —
    a text message (media_type == "") gets normalized_text == message_text,
    media_confidence == 1.0, media_failure == False, and both
    media_category and media_failure_reason set to None. media_failure_reason
    is non-None whenever media_failure is True, and always None otherwise.
    """

    message_id: str
    user_id: str
    conversation_type: str
    group_id: str
    business_id: str
    sender_user_id: str
    created_at: str
    media_type: str
    normalized_text: str
    media_confidence: float
    media_failure: bool
    media_category: str | None
    media_failure_reason: str | None
