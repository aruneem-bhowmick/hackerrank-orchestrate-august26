"""Sender-scoped input contract for deterministic safety scoring."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SafetyMessage:
    """The fixed message-field allowlist available to safety detectors.

    Receiver-scoped fields, including user_id, group membership, and prior
    engagement, are intentionally absent. from_record copies only the four
    fields required for sender-independent scoring from a loaded message row.
    """

    message_id: str
    business_id: str
    message_text: str
    forwarded_count: str

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "SafetyMessage":
        """Copy the safety-scoring allowlist from one messages.csv record."""
        return cls(
            message_id=_string_value(record, "message_id"),
            business_id=_string_value(record, "business_id"),
            message_text=_string_value(record, "message_text"),
            forwarded_count=_string_value(record, "forwarded_count"),
        )


def _string_value(record: Mapping[str, object], field: str) -> str:
    """Return a string field from a CSV-derived record, treating nulls as blank."""
    value = record.get(field, "")
    return value if isinstance(value, str) else ""
